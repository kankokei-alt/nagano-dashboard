"""宿泊旅行統計調査の「年の確定値」集計表と「広域市町村（130区分）別」参考表から、長野県分の内訳を取り込む。

推移表（pipelines/shukuhaku.py）にない内訳を、各年の Excel から長野県の行だけ抜き出す。

1) 居住地別（県内/県外）の延べ宿泊者数 … 第9表、2010〜2025年の各月
   出力: data/processed/shukuhaku_residence.parquet
     ym, total, kennai, kengai, basis
   ※ 2010年は「従業者数10人以上の施設」、2011年以降は全施設（basis 列に記録）。

2) 国籍（出身地）別の外国人延べ宿泊者数 … 参考第1表（2009年は第11表）、2009〜2025年の各月
   出力: data/processed/shukuhaku_nationality.parquet
     ym, country, value
   ※ 従業者数10人以上の施設が対象（推移表の外国人延べ宿泊者数=全施設 より少し小さい）。
     国・地域の区分は年によって 13→16→19→21 と増えている。「*」付きの参考値もそのまま使う。

3) 長野県内5エリア（広域市町村130区分）別の延べ宿泊者数・外国人延べ宿泊者数 … 2021〜2025年の各月
   出力: data/processed/shukuhaku_area.parquet（ym, area, guests, foreign）
         config/shukuhaku_areas.csv（市町村コード → エリア）

使い方:
  python pipelines/shukuhaku_detail.py   # ページからファイルを探して取得（取得済みは再利用）
"""
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://www.mlit.go.jp/kankocho/tokei_hakusyo/shukuhakutokei.html"
RAW = ROOT / "data/raw/shukuhaku"
OUT = ROOT / "data/processed"
SECTIONS = {"確定値": "kakutei", "【参考表】広域市町村（130区分）別集計": "kouiki"}
COUNTRY = {"アメリカ": "米国", "イギリス": "英国"}  # 年による表記ゆれをそろえる


def _norm(s) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s)))


def _num(v) -> float | None:
    s = _norm(v).replace(",", "").lstrip("*")
    try:
        return float(s)
    except ValueError:
        return None


def download() -> dict[str, dict[int, Path]]:
    """「確定値」「130区分」の欄にある Excel を年ごとに取得する。"""
    html = requests.get(PAGE, timeout=60).content.decode("utf-8")
    files: dict[str, dict[int, Path]] = {k: {} for k in SECTIONS.values()}
    sec = None
    for m in re.finditer(r'<(h[2-5])[^>]*>(.*?)</\1>|<a [^>]*href="([^"]+\.xlsx?)"[^>]*>(.*?)</a>', html, re.S):
        if m.group(1):
            sec = SECTIONS.get(re.sub(r"<[^>]+>|\s+", "", m.group(2)))
            continue
        y = re.search(r"(\d{4})年", re.sub(r"<[^>]+>", "", m.group(4)))
        if sec and y:
            url = urljoin(PAGE, m.group(3))
            path = RAW / f"{sec}{y.group(1)}.{url.rsplit('.', 1)[1]}"
            if not path.exists():
                RAW.mkdir(parents=True, exist_ok=True)
                path.write_bytes(requests.get(url, timeout=300).content)
            files[sec][int(y.group(1))] = path
    return files


def _month_sheets(book: pd.ExcelFile, prefix: str) -> dict[int, str]:
    """「第9表(1月)」のような月別シート名を {月: シート名} で返す（四半期・年計は除く）。"""
    out = {}
    for sh in book.sheet_names:
        m = re.fullmatch(rf"{prefix}\((\d+)月\)", _norm(sh))
        if m:
            out[int(m.group(1))] = sh
    return out


def _nagano_row(d: pd.DataFrame) -> pd.Series:
    hit = d[d.iloc[:, 0].map(_norm).str.fullmatch(r"(20)?長野県")]
    return hit.iloc[0]


def residence(book: pd.ExcelFile, year: int) -> list[dict]:
    recs = []
    for month, sh in _month_sheets(book, "第9表").items():
        d = pd.read_excel(book, sheet_name=sh, header=None)
        head = d.iloc[:7].map(_norm)
        r = next(i for i in range(len(head)) if (head.iloc[i] == "県内1)").any())
        c_in = list(head.iloc[r]).index("県内1)")
        row = _nagano_row(d)
        basis = "従業者数10人以上の施設" if "10人以上" in "".join(head.iloc[:, 1]) else "全施設"
        recs.append({"ym": pd.Timestamp(year, month, 1), "total": _num(row.iloc[1]),
                     "kennai": _num(row.iloc[c_in]), "kengai": _num(row.iloc[c_in + 1]), "basis": basis})
    return recs


def nationality(book: pd.ExcelFile, year: int) -> list[dict]:
    recs = []
    prefix = next(p for p in ["参考第1表", "第11表"] if _month_sheets(book, p))
    for month, sh in _month_sheets(book, prefix).items():
        d = pd.read_excel(book, sheet_name=sh, header=None)
        if "国籍" not in _norm(d.iloc[0, 0]):
            continue
        hr = next(i for i in range(8) if (d.iloc[i].map(_norm) == "韓国").any())
        row = _nagano_row(d)
        for j in range(2, d.shape[1]):
            name = _norm(d.iloc[hr, j])
            v = _num(row.iloc[j])
            if name and name != "nan" and v is not None:
                name = re.sub(r"\d\)$", "", name)  # 注記番号を除く
                recs.append({"ym": pd.Timestamp(year, month, 1), "country": COUNTRY.get(name, name), "value": v})
    return recs


def areas(path: Path, year: int) -> tuple[list[dict], pd.DataFrame]:
    book = pd.ExcelFile(path)
    recs = []
    for sh in book.sheet_names:
        m = re.search(r"\((\d+)月\)", _norm(sh))
        if not m:
            continue
        d = pd.read_excel(book, sheet_name=sh, header=None)
        for _, r in d[d.iloc[:, 0].map(_norm).str.match(r"^\d{2}長野県")].iterrows():
            recs.append({"ym": pd.Timestamp(year, int(m.group(1)), 1),
                         "area": re.sub(r"^\d{2}", "", _norm(r.iloc[0])),
                         "guests": _num(r.iloc[1]), "foreign": _num(r.iloc[2])})
    key = next(sh for sh in book.sheet_names if _norm(sh).endswith("1-2"))  # 「参考表1-2 広域市町村130区分表」
    t = pd.read_excel(book, sheet_name=key, header=None, skiprows=4)
    t = t[t.iloc[:, 1].map(_norm) == "長野県"]
    mapping = pd.DataFrame({"municipality_code": t.iloc[:, 2].astype(int).astype(str),
                            "municipality": t.iloc[:, 3].map(_norm), "area_full": t.iloc[:, 4].map(_norm)})
    return recs, mapping


def main() -> None:
    files = download()
    res, nat = [], []
    for year, path in sorted(files["kakutei"].items()):
        book = pd.ExcelFile(path)
        try:
            r = residence(book, year) if year >= 2010 else []
            n = nationality(book, year) if year >= 2009 else []
        except (StopIteration, IndexError) as e:
            print(f"  {year}: skip ({e!r})")
            continue
        res += r
        nat += n
        print(f"  {year}: 居住地 {len(r)}か月, 国籍 {len({x['country'] for x in n})}区分")
    r = pd.DataFrame(res).sort_values("ym")
    r.to_parquet(OUT / "shukuhaku_residence.parquet", index=False)
    n = pd.DataFrame(nat).sort_values(["ym", "country"])
    n.to_parquet(OUT / "shukuhaku_nationality.parquet", index=False)

    ar, mapping = [], None
    for year, path in sorted(files["kouiki"].items()):
        recs, mp = areas(path, year)
        ar += recs
        mapping = mp  # 最新年の対応表を使う
    a = pd.DataFrame(ar).sort_values(["area", "ym"])
    a.to_parquet(OUT / "shukuhaku_area.parquet", index=False)
    mapping["area"] = mapping.area_full.str.extract(r"^(長野県..)")[0]
    mapping.to_csv(ROOT / "config/shukuhaku_areas.csv", index=False)
    print(f"wrote residence {len(r)}行 ({r.ym.min():%Y-%m}〜{r.ym.max():%Y-%m}), "
          f"nationality {len(n)}行, area {len(a)}行 ({a.ym.min():%Y}〜{a.ym.max():%Y}, {a.area.nunique()}エリア)")


if __name__ == "__main__":
    main()

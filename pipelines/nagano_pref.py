"""長野県（山岳高原観光課）の観光統計 PDF を取り込む。

県は Excel/CSV を出しておらず PDF のみのため、pdfplumber で表を読み取る。
どちらもページから PDF のリンクを探して取得する（ファイル名が年ごとに不規則なため）。

1) 観光入込客統計（観光庁 共通基準）  … irikomi
   各年の結果 PDF 1ページ目の (1)入込客数(千人) (2)消費額単価(円) (3)観光消費額(百万円) を、
   四半期 × 区分（観光目的/訪日外国人/ビジネス目的 × 宿泊/日帰り × 県内/県外 など）の縦持ちにする。
   出力: data/processed/irikomi.parquet
     year, period(Q1〜Q4/年計), measure(visitors/unit_price/spend), purpose, stay, origin, value

2) 観光地利用者統計調査  … riyousha
   最新年の PDF から
   - 観光地ごとの明細（最新年と前年の 延利用者数・県内/県外・日帰り/宿泊・月別・観光地消費額・類型）
   - 観光地ごとの年次推移（平成22年〜最新年の延利用者数）
   出力: data/processed/riyousha_spots.parquet, data/processed/riyousha_history.parquet
   ※ PDF の単位は延利用者数が「百人」、消費額が「千円」。出力では「人」「円」に直す。

使い方:
  python pipelines/nagano_pref.py irikomi
  python pipelines/nagano_pref.py riyousha
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import pdfplumber
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/nagano"
OUT = ROOT / "data/processed"
BASE = "https://www.pref.nagano.lg.jp/kankoki/sangyo/kanko/toukei/"
ERA = {"H": 1988, "R": 2018}


def _norm(s) -> str:
    """全角→半角などをそろえ、PDF の字間スペースを取る。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s or "")))


def _num(s) -> float | None:
    s = _norm(s).replace(",", "").replace("△", "-")
    try:
        return float(s)
    except ValueError:
        return None


def _links(page: str, pattern: str) -> list[tuple[str, str]]:
    """ページ内の PDF リンク (url, リンク文字) のうち、リンク文字が pattern に合うもの。"""
    html = requests.get(urljoin(BASE, page), timeout=60).content.decode("utf-8", "replace")
    out = []
    for m in re.finditer(r'<a [^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.S):
        text = re.sub(r"<[^>]+>|\s+", "", m.group(2))
        if re.search(pattern, text):
            out.append((urljoin(urljoin(BASE, page), m.group(1)), text))
    return out


def _year_of(text: str) -> int | None:
    m = re.search(r"(平成|令和)(元|\d+)年", unicodedata.normalize("NFKC", text))
    if not m:
        return None
    return {"平成": 1988, "令和": 2018}[m.group(1)] + (1 if m.group(2) == "元" else int(m.group(2)))


def _get(url: str) -> Path:
    path = RAW / url.rsplit("/", 1)[1]
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=180)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


# ---------------------------------------------------------------- 観光入込客統計
# 15列の並び（PDF の表頭どおり）。小計は purpose ごとの合計。
IRIKOMI_COLS = [
    ("観光目的", "宿泊", "県外"), ("観光目的", "宿泊", "県内"),
    ("観光目的", "日帰り", "県外"), ("観光目的", "日帰り", "県内"), ("観光目的", "計", "計"),
    ("訪日外国人", "宿泊", "観光"), ("訪日外国人", "宿泊", "ビジネス"),
    ("訪日外国人", "日帰り", "観光"), ("訪日外国人", "日帰り", "ビジネス"), ("訪日外国人", "計", "計"),
    ("ビジネス目的", "宿泊", "県外"), ("ビジネス目的", "宿泊", "県内"),
    ("ビジネス目的", "日帰り", "県外"), ("ビジネス目的", "日帰り", "県内"), ("ビジネス目的", "計", "計"),
]
UNITS = {"visitors": 1000, "unit_price": 1, "spend": 1_000_000}
QUARTERS = {"1~3月": "Q1", "4~6月": "Q2", "7~9月": "Q3", "10~12月": "Q4"}


def _section(line: str) -> str | None:
    """「(1)観光入込客数」「(2)観光消費額単価」などの見出し行 → measure。年によって順番が違う。
    2017・2018年版は見出しに【参考値】の文字が重なって「観光入込【参客考値数】」と読まれる。"""
    if not re.match(r"^\(\d\)観光", line):
        return None
    if "単価" in line:
        return "unit_price"
    if "消費額" in line:
        return "spend"
    if "入込" in line:
        return "visitors"
    return None


def parse_irikomi(path: Path, year: int) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(pg.dedupe_chars().extract_text() or "" for pg in pdf.pages)
    text = unicodedata.normalize("NFKC", text).replace("～", "~").replace("〜", "~")
    recs, measure = [], None
    for line in text.splitlines():
        line = re.sub(r"年 (計|平均)", r"年\1", line.strip())
        sec = _section(line.replace(" ", ""))
        if sec:
            measure = sec
            continue
        parts = line.split()
        if measure is None or len(parts) != 16:
            continue
        label = parts[0]
        if label in QUARTERS:
            period = QUARTERS[label]
        elif label in ("年計", "年平均") or (re.fullmatch(r"[RH](元|\d+)年(計|平均)", label)
                                              and _era_year(label[:-3] if label.endswith("平均") else label[:-2]) == year):
            period = "年計"
        else:
            continue  # 前年の年計は、その年の PDF から取る
        for (purpose, stay, origin), v in zip(IRIKOMI_COLS, parts[1:]):
            x = _num(v)
            if x is None and v in "-－":
                x = 0.0  # 「-」は該当なし
            if measure == "unit_price" and stay == "計":
                continue  # 単価の小計欄は空欄
            recs.append((year, period, measure, purpose, stay, origin, None if x is None else x * UNITS[measure]))
    df = pd.DataFrame(recs, columns=["year", "period", "measure", "purpose", "stay", "origin", "value"])
    df = df.drop_duplicates(["year", "period", "measure", "purpose", "stay", "origin"])  # 2ページ目の再掲など
    if df.empty or not {"visitors", "spend"} <= set(df[df.period == "年計"].measure):
        raise ValueError("年計の行が読めない")
    return df


def _era_year(label: str) -> int | None:
    m = re.fullmatch(r"([RH])(元|\d+)", label.replace("Ｒ", "R").replace("Ｈ", "H"))
    if not m:
        return None
    return ERA[m.group(1)] + (1 if m.group(2) == "元" else int(m.group(2)))


def irikomi() -> None:
    parts = []
    for url, text in _links("irikomi.html", r"観光入込客統計結果"):
        year = _year_of(text)
        try:
            parts.append(parse_irikomi(_get(url), year))
            print(f"  {year}: ok")
        except Exception as e:  # 古い年は様式が違うので読めたものだけ使う
            print(f"  {year}: skip ({e})")
    df = pd.concat(parts, ignore_index=True).sort_values(["year", "measure", "period"])
    df.to_parquet(OUT / "irikomi.parquet", index=False)
    tot = df[(df.period == "年計") & (df.stay == "計")].groupby(["year", "measure"]).value.sum().unstack()
    print(f"wrote irikomi.parquet ({len(df):,} rows)\n{(tot[['visitors', 'spend']] / [1e3, 1e6]).round(0)}")


# ---------------------------------------------------------------- 観光地利用者統計調査
MONTHS = [f"m{i:02d}" for i in range(1, 13)]
SPOT_COLS = ["total", "_chg", "kennai", "kengai", "higaeri", "shukuhaku", *MONTHS, "spend"]


def _muni_codes() -> dict[str, str]:
    m = pd.read_csv(ROOT / "config/municipalities.csv", dtype={"code": str})
    return dict(zip(m.name, m.code))


def _spot_name(s) -> str:
    return _norm(s)  # 改行は表の折り返し


def _hist_years(labels) -> list[int | None]:
    """年次推移の表頭（「21年」…「30年」「R元年」「2年」…）を西暦に。「元」より前は平成、以降は令和。"""
    out, era = [], ERA["H"]
    for label in labels:
        m = re.search(r"(元|\d+)年", _norm(label or ""))
        if not m:
            out.append(None)
            continue
        if m.group(1) == "元":
            era = ERA["R"]
        out.append(era + (1 if m.group(1) == "元" else int(m.group(1))))
    return out


def _col(t, label: str) -> int:
    return next((j for r in t[:4] for j, c in enumerate(r) if _norm(c) == label), 0)


def parse_riyousha(path: Path, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """year はその PDF の調査年。明細表の各行は「今年」「前年」の順に2段で並ぶ。"""
    spots, hist = [], []
    codes = _muni_codes()
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # 太字を重ね打ちした行は同じ文字が2つずつ読まれるので、重なった文字を除く
            for t in page.dedupe_chars().extract_tables():
                header = " ".join(_norm(c) for r in t[:4] for c in r if c)
                if "観光地類型" in header:
                    kind = "spots"
                elif "観光地延利用者数の推移" in header:
                    kind = "hist"
                    years_row = next(r for r in t[:4] if any(_norm(c).endswith("年") for c in r if c))
                    hist_years = _hist_years(years_row[_col(t, "市町村名") + 2:])
                else:
                    continue
                muni = None
                # 「市町村名」の列位置（年によって左端にページ番号の列がある）
                off = _col(t, "市町村名")
                for r in t:
                    m_cell, name_cell = r[off], r[off + 1]
                    if m_cell and _norm(m_cell) not in ("〃", "市町村名"):
                        muni = _norm(m_cell)
                    if not name_cell or _norm(name_cell) in ("観光地名",) or muni is None:
                        continue
                    if muni not in codes:
                        continue  # 地域振興局計などの小計行
                    name = _spot_name(name_cell)
                    if kind == "spots":
                        yrs = str(r[off + 2]).split("\n")
                        cols = [str(c or "").split("\n") for c in r[off + 3: off + 3 + len(SPOT_COLS)]]
                        for i, y in enumerate(yrs[:2]):
                            vals = {k: _num(c[i]) if i < len(c) else None for k, c in zip(SPOT_COLS, cols)}
                            if vals["total"] is None:
                                continue
                            spots.append({"year": year - i,
                                          "municipality_code": codes[muni], "municipality": muni, "spot": name,
                                          "category": _norm(r[off + 3 + len(SPOT_COLS)]), **vals})
                    else:
                        for y, cell in zip(hist_years, r[off + 2:]):
                            v = _num(str(cell or "").split("\n")[0])
                            if y and v is not None:
                                hist.append((y, codes[muni], muni, name, v * 100))
    s = pd.DataFrame(spots).drop(columns="_chg")
    for c in ["total", "kennai", "kengai", "higaeri", "shukuhaku", *MONTHS]:
        s[c] = s[c] * 100  # 百人 → 人
    s["spend"] = s["spend"] * 1000  # 千円 → 円
    h = pd.DataFrame(hist, columns=["year", "municipality_code", "municipality", "spot", "visitors"])
    return s, h


def riyousha() -> None:
    """各年の明細は、その年の PDF（なければ翌年の PDF の「前年」行）から取る。
    合計が最新 PDF の年次推移（県の公表値と一致）と 0.5% 以内で合う年だけを採用する。"""
    links = sorted(((u, _year_of(t)) for u, t in _links("riyousya.html", r"観光地利用者統計調査結果")),
                   key=lambda x: -(x[1] or 0))
    parsed = {}
    for url, year in links:
        try:
            parsed[year] = parse_riyousha(_get(url), year)
        except Exception as e:  # 古い年は様式が違う
            print(f"  {year}年版: 読めない ({type(e).__name__})")
    latest = max(parsed)
    h = parsed[latest][1]
    target = h.groupby("year").visitors.sum()
    spots = []
    for year in sorted(target.index, reverse=True):
        for src in (year, year + 1):  # その年の版 → 翌年の版の「前年」行
            if src not in parsed:
                continue
            s = parsed[src][0]
            s = s[s.year == year]
            if len(s) and abs(s.total.sum() / target[year] - 1) < 0.005:
                spots.append(s.assign(source=f"{src}年版"))
                print(f"  {year}: {len(s)} 観光地 / {s.total.sum() / 1e4:,.0f} 万人 / {s.spend.sum() / 1e8:,.0f} 億円（{src}年版）")
                break
        else:
            print(f"  {year}: 明細なし（公表値と合う表が読めない）")
    s = pd.concat(spots, ignore_index=True)
    s.to_parquet(OUT / "riyousha_spots.parquet", index=False)
    h.to_parquet(OUT / "riyousha_history.parquet", index=False)
    print(f"  年次推移: {h.spot.nunique()} 観光地, {h.year.min()}〜{h.year.max()}（{latest}年版）")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("what", choices=["irikomi", "riyousha"])
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {"irikomi": irikomi, "riyousha": riyousha}[a.what]()


if __name__ == "__main__":
    sys.exit(main())

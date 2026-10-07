"""日本観光振興協会「デジタル観光統計オープンデータ」を取り込む。

スマートフォンの位置情報から推計した、都道府県・市区町村ごとの月別「観光来訪者数」（2021年1月〜）。
自宅から20km以上離れた観光地点に滞在した人を数え、同じ日に同じ市町村の観光地点を何か所回っても1人と数える。
（県の「観光地利用者統計調査」の観光地ごとの延べ人数を足したものとは違い、市町村の人数として使える。）

公表ページ: https://www.nihon-kankou.or.jp/home/jigyou/research/d-toukei/
  - 年ごとのファイル（pref2021.csv … / city2021.csv …）… 年1回、地点の変更を反映して再集計したもの
  - 月ごとのファイル（pref202601.csv …）… 今年の分
  列: 年,月,年月,地域区分,データ区分,(都道府県コード,都道府県名,)地域コード,地域名称,人数
ライセンス: CC BY 4.0（非営利の利用）。改変して使うときは「デジタル観光統計オープンデータを加工して作成」と明記する。

取り込み元（上から順に使えるもの）:
  1. 公表ページの CSV（d2eveo6c5xeu3l.cloudfront.net。環境のネットワーク設定で許可が必要）
  2. 公表 CSV を Google スプレッドシートにまとめた写し（data/raw/digital/drive_*.xlsx。シート pref / city_nagano）

公表値との照合:
  協会のニュースリリースに毎月載る「観光来訪者数（都道府県来訪者数の全国計）」（config/digital_published.csv。
  月ごとに最新のリリースの値）と、取り込んだ47都道府県の合計を月ごとに比べる（百万人の小数1桁で一致すること）。
  合わない月・照合できる公表値がない月は使わず、理由を data/processed/checks/digital.csv に残す。
  あわせて、長野県の人数が77市町村の合計を超えていないこと（市町村をまたぐと重複して数えるため、県≦市町村の合計）も確かめる。
  市町村の行がない月は、人数が少なく公表されていない月として扱う（0人にはしない）。

出力:
  data/processed/digital_city.parquet … municipality_code, ym, visitors（照合で採用した月だけ）
  data/processed/digital_pref.parquet … pref_code, pref, ym, visitors（47都道府県、採用した月だけ）
  data/processed/checks/digital.csv

使い方: python pipelines/digital.py
"""
import io
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://www.nihon-kankou.or.jp/home/jigyou/research/d-toukei/"
RAW = ROOT / "data/raw/digital"
PUBLISHED = ROOT / "config/digital_published.csv"
OUT_CITY = ROOT / "data/processed/digital_city.parquet"
OUT_PREF = ROOT / "data/processed/digital_pref.parquet"
CHECKS = ROOT / "data/processed/checks/digital.csv"
TOL = 0.051  # 百万人。リリースは小数1桁なので、四捨五入の差まで許す


# ---------- 1. 公表ページの CSV ----------

def _read_csv(b: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp932"):
        try:
            return pd.read_csv(io.BytesIO(b), encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("文字コードを判別できません")


def from_official() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    html = requests.get(PAGE, timeout=60).text
    urls = sorted(set(re.findall(r'https://[^"]+/(?:pref|city)/(?:pref|city)\d{4,6}\.csv', html)))
    if not urls:
        raise RuntimeError("公表ページに CSV のリンクが見つかりません")
    RAW.mkdir(parents=True, exist_ok=True)
    frames = {"pref": [], "city": []}
    for u in urls:
        r = requests.get(u, timeout=120)
        r.raise_for_status()
        (RAW / u.rsplit("/", 1)[1]).write_bytes(r.content)
        df = _read_csv(r.content)
        df["file"] = u.rsplit("/", 1)[1]
        frames["pref" if "/pref/" in u else "city"].append(df)
    pref, city = pd.concat(frames["pref"]), pd.concat(frames["city"])
    # 同じ月が年ファイルと月ファイルの両方にあれば、再集計された年ファイルを使う
    for d in (pref, city):
        d["annual"] = d.file.str.match(r"^(pref|city)\d{4}\.csv$")
    return pref, city, "公表ページの CSV"


# ---------- 2. Google スプレッドシートの写し ----------

def from_drive() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    files = sorted(RAW.glob("drive_*.xlsx"))
    if not files:
        raise FileNotFoundError(f"{RAW} に drive_*.xlsx がありません")
    path = files[-1]
    pref = pd.read_excel(path, sheet_name="pref")
    city = pd.read_excel(path, sheet_name="city_nagano")
    for d in (pref, city):
        d["file"] = path.name
        d["annual"] = False
    return pref, city, f"公表 CSV の写し（{path.name}）"


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["データ区分"] == "観光来訪者数"].copy()
    df["ym"] = pd.to_datetime(dict(year=df["年"].astype(int), month=df["月"].astype(int), day=1))
    df["code"] = df["地域コード"].astype(float).astype(int).astype(str)
    df = df.rename(columns={"地域名称": "name", "人数": "visitors"})
    df = df.sort_values("annual").drop_duplicates(["code", "ym"], keep="last")
    return df[["code", "name", "ym", "visitors", "file"]]


def main() -> None:
    try:
        pref, city, source = from_official()
    except Exception as e:  # ネットワークで止められているときなど
        print(f"公表ページの CSV を取得できませんでした（{type(e).__name__}）。写しを使います。")
        pref, city, source = from_drive()
    pref, city = tidy(pref), tidy(city)
    print(f"取り込み元: {source}")

    muni = pd.read_csv(ROOT / "config/municipalities.csv", dtype={"code": str})
    codes = set(muni.code)
    city["municipality_code"] = city.code.str[:5]  # 6桁（検査数字つき）でも5桁にそろえる
    nag = city[city.municipality_code.isin(codes)]
    nat = pref.groupby("ym").visitors.sum() / 1e6
    pn = pref[pref.code == "20"].set_index("ym").visitors
    pub = pd.read_csv(PUBLISHED, comment="#")
    pub["ym"] = pd.to_datetime(pub.ym + "-01")
    pub = pub.set_index("ym")

    checks = []
    for ym in sorted(set(nat.index) | set(nag.ym)):
        g = nag[nag.ym == ym]
        reasons = []
        n_pref = pref[pref.ym == ym].code.nunique()
        if n_pref != 47:
            reasons.append(f"都道府県がそろっていない（{n_pref}）")
        if ym not in pub.index:
            reasons.append("照合できる公表値（ニュースリリースの全国計）がない")
        elif abs(nat.get(ym, 0) - pub.loc[ym, "national_million"]) > TOL:
            reasons.append(f"全国計が公表値と合わない（取り込み {nat.get(ym, 0):.1f} / 公表 {pub.loc[ym, 'national_million']:.1f} 百万人。"
                           "協会の再集計の前の値と考えられる）")
        if ym not in pn.index:
            reasons.append("長野県の値がない")
        elif pn[ym] > g.visitors.sum():
            reasons.append("長野県の人数が市町村の合計を超えている")
        checks.append({
            "ym": ym.strftime("%Y-%m"), "source": source, "national_million": round(nat.get(ym, float("nan")), 2),
            "published_million": pub.national_million.get(ym), "release_date": pub.release_date.get(ym),
            "nagano_pref": pn.get(ym), "nagano_muni_sum": int(g.visitors.sum()), "municipalities": g.municipality_code.nunique(),
            "missing": "・".join(muni.set_index("code").name[sorted(codes - set(g.municipality_code))]),
            "adopted": not reasons, "reason": "・".join(reasons),
        })
    ck = pd.DataFrame(checks)
    good = pd.to_datetime(ck[ck.adopted].ym + "-01")
    out = nag[nag.ym.isin(good)][["municipality_code", "ym", "visitors"]].sort_values(["municipality_code", "ym"])
    pref_out = (pref[pref.ym.isin(good)].assign(pref_code=lambda d: d.code.astype(int)).rename(columns={"name": "pref"})
                [["pref_code", "pref", "ym", "visitors"]].sort_values(["pref_code", "ym"]))

    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_CITY, index=False)
    pref_out.to_parquet(OUT_PREF, index=False)
    ck.to_csv(CHECKS, index=False)
    print(ck[["ym", "national_million", "published_million", "municipalities", "adopted", "reason"]].to_string(index=False))
    print(f"採用 {ck.adopted.sum()}か月 / {len(ck)}か月")
    print(f"wrote {OUT_CITY} ({len(out)} rows), {OUT_PREF} ({len(pref_out)} rows)")


if __name__ == "__main__":
    main()

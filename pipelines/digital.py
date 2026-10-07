"""日本観光振興協会「デジタル観光統計オープンデータ」を取り込む。

スマートフォンの位置情報から推計した、都道府県・市区町村ごとの月別「観光来訪者数」（2021年1月〜）。
自宅から20km以上離れた観光地点に滞在した人を数え、同じ日に同じ市町村の観光地点を何か所回っても1人と数える。
（県の「観光地利用者統計調査」の観光地ごとの延べ人数を足したものとは違い、市町村単位の人数として使える。）

公表ページ: https://www.nihon-kankou.or.jp/home/jigyou/research/d-toukei/
  - 年ごとのファイル（pref2021.csv … pref2025.csv / city2021.csv …）… 年1回、各地域の地点変更を反映して再集計したもの
  - 月ごとのファイル（pref202601.csv …）… 今年の速報
  列: 年,月,年月,地域区分,データ区分,地域コード,地域名称,人数
ライセンス: CC BY 4.0（非営利の利用）。改変して使うときは「デジタル観光統計オープンデータを加工して作成」と明記する。

照合（公表値に合計がないため、ファイルどうしの整合を確かめる）:
  1. 各月、長野県の77市町村がそろっていること
  2. 長野県の人数（県単位で1日1人）が、市町村の人数の合計（市町村をまたぐと重複して数える）を超えないこと
  3. 年ごとのファイルは12か月そろっていること
  合わない月は使わず、理由を data/processed/checks/digital.csv に残す。

出力:
  data/processed/digital_city.parquet … municipality_code, ym, visitors, file
  data/processed/digital_pref.parquet … pref_code, pref, ym, visitors, file（47都道府県）
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
OUT_CITY = ROOT / "data/processed/digital_city.parquet"
OUT_PREF = ROOT / "data/processed/digital_pref.parquet"
CHECKS = ROOT / "data/processed/checks/digital.csv"


def links() -> list[str]:
    html = requests.get(PAGE, timeout=60).text
    return sorted(set(re.findall(r'https://[^"]+/(?:pref|city)/(?:pref|city)\d{4,6}\.csv', html)))


def fetch(url: str) -> pd.DataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / url.rsplit("/", 1)[1]
    if not path.exists() or re.search(r"\d{6}\.csv$", path.name) is None:  # 年ファイルは再集計で差し替わるので毎回取り直す
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    b = path.read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            df = pd.read_csv(io.BytesIO(b), encoding=enc, dtype={"地域コード": str})
            break
        except UnicodeDecodeError:
            continue
    df["file"] = path.name
    return df


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["データ区分"] == "観光来訪者数"].copy()
    df["ym"] = pd.to_datetime(dict(year=df["年"], month=df["月"], day=1))
    df["code"] = df["地域コード"].str.strip()
    return df.rename(columns={"地域名称": "name", "人数": "visitors"})[["code", "name", "ym", "visitors", "file"]]


def main() -> None:
    urls = links()
    print(f"{len(urls)} files")
    pref = tidy(pd.concat([fetch(u) for u in urls if "/pref/" in u]))
    city = tidy(pd.concat([fetch(u) for u in urls if "/city/" in u]))
    # 同じ月が年ファイルと月ファイルの両方にあれば、再集計された年ファイルを使う
    for d in (pref, city):
        d["annual"] = d.file.str.match(r"^(pref|city)\d{4}\.csv$")
    pref = pref.sort_values("annual").drop_duplicates(["code", "ym"], keep="last")
    city = city.sort_values("annual").drop_duplicates(["code", "ym"], keep="last")

    muni = pd.read_csv(ROOT / "config/municipalities.csv", dtype={"code": str})
    codes = set(muni.code)
    city["municipality_code"] = city.code.str[:5]  # 6桁（検査数字つき）でも5桁にそろえる
    nag = city[city.municipality_code.isin(codes)]
    pn = pref[pref.code.astype(int) == 20].set_index("ym").visitors

    checks = []
    for ym, g in nag.groupby("ym"):
        reasons = []
        if g.municipality_code.nunique() < len(codes):
            miss = sorted(codes - set(g.municipality_code))
            reasons.append(f"市町村がそろっていない（{len(miss)}市町村なし）")
        if ym not in pn.index:
            reasons.append("同じ月の長野県の値がない")
        elif pn[ym] > g.visitors.sum():
            reasons.append("長野県の人数が市町村の合計を超えている")
        checks.append({"ym": ym.strftime("%Y-%m"), "file": g.file.iloc[0], "municipalities": g.municipality_code.nunique(),
                       "muni_sum": int(g.visitors.sum()), "pref": int(pn.get(ym, -1)),
                       "adopted": not reasons, "reason": "・".join(reasons)})
    ck = pd.DataFrame(checks)
    for f, g in nag.groupby("file"):
        if re.match(r"city\d{4}\.csv$", f) and g.ym.nunique() != 12:
            ck.loc[ck.file == f, ["adopted", "reason"]] = [False, "年ファイルの月がそろっていない"]
    good = pd.to_datetime(ck[ck.adopted].ym)
    out = nag[nag.ym.isin(good)][["municipality_code", "ym", "visitors", "file"]].sort_values(["municipality_code", "ym"])
    pref_out = pref.assign(pref_code=pref.code.astype(int)).rename(columns={"name": "pref"})[
        ["pref_code", "pref", "ym", "visitors", "file"]].sort_values(["pref_code", "ym"])

    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_CITY, index=False)
    pref_out.to_parquet(OUT_PREF, index=False)
    ck.to_csv(CHECKS, index=False)
    print(ck.to_string())
    print(f"wrote {OUT_CITY} ({len(out)} rows), {OUT_PREF} ({len(pref_out)} rows)")


if __name__ == "__main__":
    main()

"""長野県の市町村別人口（国勢調査）を e-Stat API から取り込む。

e-Stat「社会・人口統計体系 市区町村データ」（statsDataId 0000020201）の A1101 総人口。
市町村ページの「住民1人あたりの観光地利用者数」に使う。

公表値との照合: 77市町村の合計が、「社会・人口統計体系 都道府県データ」（0000010101）の長野県の総人口と一致すること。
合わない年は使わない。

出力:
  data/processed/population.parquet … municipality_code, year, population
  data/processed/checks/population.csv

使い方（ESTAT_APP_ID が必要。値は表示しない・リポジトリに書かない）:
  python pipelines/population.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from estat import get_data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/population.parquet"
CHECKS = ROOT / "data/processed/checks/population.csv"


def main() -> None:
    codes = pd.read_csv(ROOT / "config/municipalities.csv", dtype={"code": str}).code.tolist()
    m = get_data("0000020201", cdCat01="A1101", cdArea=",".join(codes))
    m["year"] = m.time.astype(str).str[:4].astype(int)
    m = m[m.year >= 2010]
    p = get_data("0000010101", cdCat01="A1101", cdArea="20000")
    p["year"] = p.time.astype(str).str[:4].astype(int)
    pref = p.set_index("year").value
    checks = []
    for y, g in m.groupby("year"):
        ok = len(g) == len(codes) and y in pref.index and abs(g.value.sum() - pref[y]) < 1
        checks.append({"year": y, "municipalities": len(g), "sum": g.value.sum(), "pref_total": pref.get(y),
                       "adopted": ok, "reason": "" if ok else "市町村の合計が県の総人口と合わない、または市町村がそろっていない"})
        print(f"  {y}: {len(g)}市町村 合計 {g.value.sum():,.0f} / 県 {pref.get(y, float('nan')):,.0f} → {'採用' if ok else '除外'}")
    good = [c["year"] for c in checks if c["adopted"]]
    out = (m[m.year.isin(good)].rename(columns={"area": "municipality_code", "value": "population"})
           [["municipality_code", "year", "population"]].sort_values(["municipality_code", "year"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    pd.DataFrame(checks).to_csv(CHECKS, index=False)
    print(f"wrote {OUT} ({len(out)} rows)")


if __name__ == "__main__":
    main()

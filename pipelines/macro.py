"""稼働率予測の手がかりになる、全国の暮らし・景気の月次指標を e-Stat API から取り込む。

  cpi_all      消費者物価指数 総合（2020年=100, 全国）                … 物価の上がり方（実質の負担感）
  cpi_hotel    消費者物価指数 宿泊料（2020年=100, 全国）              … 宿泊料金の上がり方
  ww_travel_now / ww_travel_out   景気ウォッチャー 旅行・交通関連の現状判断DI / 先行き判断DI（全国, 原数値）
  ww_all_now / ww_all_out         景気ウォッチャー 合計の現状判断DI / 先行き判断DI（全国, 原数値）
  ww_koshinetsu_now / _out        景気ウォッチャー 甲信越地方 合計の現状判断DI / 先行き判断DI
  consumer_confidence             消費者態度指数（景気動向指数の個別系列, 季節調整値）

公表値との照合（合わない月は使わずに理由を記録）:
  - 消費者物価指数: 指数から計算した前年同月比が、e-Stat の表の「前年同月比」と ±0.15% 以内
    （公表の前年同月比は丸める前の指数から計算されるため、小数1桁の指数からはわずかにずれる）。
    基準改定の年（2010・2015・2020年）は公表の前年同月比が旧基準の指数で計算されているので照合の対象外。
    使うのは 2005年以降
  - 景気ウォッチャー: 「分野・業種別DI」の合計と「地域別DIの推移」の全国が一致
  - 消費者態度指数: 照合できる別の表がないので、e-Stat の値をそのまま使う（その旨を記録）

出力:
  data/processed/macro_monthly.parquet … ym, indicator, value
  data/processed/checks/macro.csv

使い方（ESTAT_APP_ID が必要。値は表示しない・リポジトリに書かない）:
  python pipelines/macro.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from estat import get_data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/macro_monthly.parquet"
CHECKS = ROOT / "data/processed/checks/macro.csv"
START = pd.Timestamp("2005-01-01")
CPI, WW_FIELD, WW_AREA, CI = "0003427113", "0003348425", "0003348426", "0003446462"


def _ym(code: pd.Series) -> pd.Series:
    """e-Stat の時間コード（例 2026000808）→ 月初の日付。年の値（月=00）は NaT。"""
    s = code.astype(str)
    month = s.str[6:8].astype(int)
    return pd.to_datetime(dict(year=s.str[:4].astype(int), month=month.where(month > 0, 1), day=1)).where(month > 0)


def cpi() -> tuple[pd.DataFrame, list[dict]]:
    d = get_data(CPI, cdArea="00000", cdCat01="0001,0139", cdTab="1,3")
    d["ym"] = _ym(d.time)
    d = d.dropna(subset=["ym"])
    w = d.pivot_table(index=["cat01", "ym"], columns="tab", values="value")
    out, checks = [], []
    for code, name in [("0001", "cpi_all"), ("0139", "cpi_hotel")]:
        x = w.loc[code].sort_index()
        x = x[x.index >= START]
        calc = (x["1"] / x["1"].shift(12, freq="MS").reindex(x.index) - 1) * 100
        diff = (calc - x["3"]).dropna()
        diff = diff[diff.index.year % 5 != 0]  # 基準改定の年は旧基準で計算されているので照合しない
        bad = diff[diff.abs() > 0.15]
        checks.append({"indicator": name, "months": len(diff), "mismatch": len(bad),
                       "detail": "" if bad.empty else "前年同月比が公表値と合わない月: " + ", ".join(f"{t:%Y-%m}" for t in bad.index)})
        v = x["1"].drop(bad.index)
        out.append(pd.DataFrame({"ym": v.index, "indicator": name, "value": v.values}))
    return pd.concat(out), checks


def watcher() -> tuple[pd.DataFrame, list[dict]]:
    f = get_data(WW_FIELD, cdCat01="100,380", cdCat02="100,110")
    a = get_data(WW_AREA, cdArea="00000,50100", cdCat01="100", cdCat02="100,110")
    for d in (f, a):
        d["ym"] = _ym(d.time)
    names = {("100", "100"): "ww_all_now", ("100", "110"): "ww_all_out",
             ("380", "100"): "ww_travel_now", ("380", "110"): "ww_travel_out"}
    f["indicator"] = [names[(c1, c2)] for c1, c2 in zip(f.cat01, f.cat02)]
    # 照合: 分野別の「合計」＝ 地域別の「全国」
    nat = a[a.area == "00000"].set_index(["ym", "cat02"]).value
    tot = f[f.cat01 == "100"].set_index(["ym", "cat02"]).value
    both = pd.concat([tot.rename("field"), nat.rename("area")], axis=1).dropna()
    bad = both[(both.field - both.area).abs() > 0.05]
    checks = [{"indicator": "景気ウォッチャー（全国 合計）", "months": both.index.get_level_values(0).nunique(),
               "mismatch": bad.index.get_level_values(0).nunique(),
               "detail": "" if bad.empty else "分野別表と地域別表の全国が合わない月: "
               + ", ".join(sorted({f"{t:%Y-%m}" for t, _ in bad.index}))}]
    drop = set(bad.index.get_level_values(0))
    k = a[a.area == "50100"].copy()
    k["indicator"] = k.cat02.map({"100": "ww_koshinetsu_now", "110": "ww_koshinetsu_out"})
    out = pd.concat([f, k])[["ym", "indicator", "value"]]
    out = out[~out.ym.isin(drop)]  # 照合で合わなかった月は使わない
    return out, checks


def confidence() -> tuple[pd.DataFrame, list[dict]]:
    d = get_data(CI, cdCat01="1060")
    d["ym"] = _ym(d.time)
    d = d.dropna(subset=["ym", "value"])
    return (pd.DataFrame({"ym": d.ym, "indicator": "consumer_confidence", "value": d.value}),
            [{"indicator": "consumer_confidence", "months": len(d), "mismatch": 0,
              "detail": "照合できる別の表がないため、e-Stat（景気動向指数 個別系列）の値をそのまま使用"}])


def main() -> None:
    parts, checks = [], []
    for fn in (cpi, watcher, confidence):
        df, c = fn()
        parts.append(df)
        checks += c
        for x in c:
            print(f"  {x['indicator']}: {x['months']}か月を照合, 不一致 {x['mismatch']} {x['detail'][:80]}")
    df = pd.concat(parts).dropna()
    df = df[df.ym >= START].sort_values(["indicator", "ym"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    pd.DataFrame(checks).to_csv(CHECKS, index=False)
    print(df.groupby("indicator").ym.agg(["min", "max", "count"]))


if __name__ == "__main__":
    main()

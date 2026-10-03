"""日別・月別の祝日/連休カレンダーを作る（需要予測の説明変数にも使う）。

出典: 内閣府「国民の祝日」（jpholiday パッケージ経由）
出力:
  data/processed/calendar_daily.parquet
  data/processed/calendar_monthly.parquet  … 月ごとの休日数・3連休以上の回数など
"""
from pathlib import Path

import jpholiday
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
START, END = "2010-01-01", "2028-01-31"  # 年末年始の連休が途切れないよう1月まで


def main() -> None:
    d = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
    d["holiday_name"] = d.date.map(lambda x: jpholiday.is_holiday_name(x.date()))
    d["is_holiday"] = d.holiday_name.notna()
    # 年末年始（12/29〜1/3）は行政・企業の休みが一般的なので休日扱いにする
    md = d.date.dt.strftime("%m%d")
    d["is_newyear"] = (md >= "1229") | (md <= "0103")
    d["is_off"] = (d.date.dt.dayofweek >= 5) | d.is_holiday | d.is_newyear

    # 連続する休日のかたまり（連休）の長さ
    block = (d.is_off != d.is_off.shift()).cumsum()
    d["off_run"] = d.groupby(block).is_off.transform("size").where(d.is_off, 0)

    d.to_parquet(ROOT / "data/processed/calendar_daily.parquet", index=False)

    d["ym"] = d.date.dt.to_period("M")
    run_start = d.is_off & ~d.is_off.shift(fill_value=False)
    m = d.assign(long_weekend=run_start & (d.off_run >= 3)).groupby("ym").agg(
        days=("date", "size"),
        off_days=("is_off", "sum"),
        holidays=("is_holiday", "sum"),
        long_weekends=("long_weekend", "sum"),
        max_off_run=("off_run", "max"),
    )
    m.index = m.index.to_timestamp()
    m.reset_index().rename(columns={"ym": "month"}).to_parquet(
        ROOT / "data/processed/calendar_monthly.parquet", index=False
    )
    print(m.tail(15))


if __name__ == "__main__":
    main()

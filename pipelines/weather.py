"""気象庁「過去の気象データ検索」から、県内の主要地点の月別の気温・降雪量・最深積雪を取り込む。

地点は config/weather_stations.csv（気象台・特別地域気象観測所=s、アメダス=a）。
各地点・各年の「月ごとの値」ページ（monthly_s1 / monthly_a1）の表を読む。

値の記号（気象庁の凡例）:
  ")"  準正常値（欠測が許容範囲内）… 使う
  "]"  資料不足値 … 使わない（欠損にする）
  "--" 該当現象なし … 降雪・積雪は 0
  "///" "×" 空欄 … 観測していない・欠測

公表値との照合（合わない年は使わずに理由を記録）:
  - 気温: 12か月そろった年の月平均気温の平均が、「年ごとの値」ページ（annually_s / annually_a）の
    年平均気温と ±0.15℃ 以内（月の日数の違いで少しずれるため）
  - 降雪・積雪: 寒候年（前年8月〜7月）ごとに、月の降雪量の合計・最深積雪の最大が年ごとの値と一致
  合わない年（寒候年）は、その年の該当する値を欠損にして data/processed/checks/weather.csv に理由を残す。

出力:
  data/processed/weather_monthly.parquet … ym, station, temp_mean(℃), snowfall(cm), snow_depth_max(cm)
  data/processed/checks/weather.csv

使い方:
  python pipelines/weather.py            # 2009年〜今年（取得済みの年はキャッシュを使い、今年と前年は取り直す）
  python pipelines/weather.py --from 2015
"""
import argparse
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STATIONS = ROOT / "config/weather_stations.csv"
RAW = ROOT / "data/raw/jma"
OUT = ROOT / "data/processed/weather_monthly.parquet"
CHECKS = ROOT / "data/processed/checks/weather.csv"
BASE = "https://www.data.jma.go.jp/stats/etrn/view/"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nagano-dashboard data pipeline"}

# 表の列位置（0=月 or 年）。地点の種類で列の並びが違う
COLS = {
    "s": {"temp_mean": 7, "snowfall": 21, "snow_depth_max": 23},
    "a": {"temp_mean": 5, "snowfall": 18, "snow_depth_max": 20},
}
SNOW = ("snowfall", "snow_depth_max")


def _get(url: str, path: Path, refresh: bool) -> str:
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r.content.decode("utf-8"), encoding="utf-8")
    time.sleep(1)  # 気象庁のサーバーに負担をかけない
    return path.read_text(encoding="utf-8")


def _rows(html: str) -> list[list[str]]:
    parts = re.split(r"id=.tablefix1.", html)
    if len(parts) < 2:
        return []
    t = parts[1][: parts[1].index("</table>")]
    return [[re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
            for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)]


def _val(s: str, snow: bool) -> tuple[float | None, str]:
    """セルの文字列 → (値, 品質)。"""
    s = s.replace("　", " ").strip()
    if s == "--":
        return (0.0, "正常") if snow else (None, "なし")
    if s.endswith("]"):
        return None, "資料不足"
    q = "準正常" if s.endswith(")") else "正常"
    m = re.match(r"^-?\d+(\.\d+)?", s)
    return (float(m.group(0)), q) if m else (None, "欠測")


def _check_header(rows: list[list[str]], kind: str) -> None:
    head = " ".join(" ".join(r) for r in rows[:3])
    if "降雪" not in head or "最深積雪" not in head:
        raise RuntimeError(f"気象庁の表の見出しが想定と違います（{kind}）。列の位置を確認してください。")


def monthly(st: pd.Series, year: int, refresh: bool) -> list[dict]:
    url = f"{BASE}monthly_{st.kind}1.php?prec_no={st.prec_no}&block_no={st.block_no}&year={year}&month=&day=&view="
    rows = _rows(_get(url, RAW / f"monthly_{st.block_no}_{year}.html", refresh))
    if not rows:
        return []
    _check_header(rows, st.kind)
    recs = []
    for r in rows[3:]:
        if not r or not r[0].isdigit():
            continue
        rec = {"ym": pd.Timestamp(year, int(r[0]), 1), "station": st.station}
        for k, j in COLS[st.kind].items():
            v, q = _val(r[j], k in SNOW) if j < len(r) else (None, "欠測")
            rec[k], rec[f"{k}_q"] = v, q
        recs.append(rec)
    return recs


def annual(st: pd.Series, refresh: bool) -> pd.DataFrame:
    url = f"{BASE}annually_{st.kind}.php?prec_no={st.prec_no}&block_no={st.block_no}&year=&month=&day=&view="
    rows = _rows(_get(url, RAW / f"annually_{st.block_no}.html", refresh))
    _check_header(rows, st.kind)
    recs = []
    for r in rows[3:]:
        if r and r[0].isdigit():
            recs.append({"year": int(r[0]), **{k: _val(r[j], k in SNOW) for k, j in COLS[st.kind].items()}})
    return pd.DataFrame(recs).set_index("year")


def validate(m: pd.DataFrame, ann: pd.DataFrame, station: str) -> tuple[pd.DataFrame, list[dict]]:
    """年ごとの値と照合し、合わない年の値を欠損にする。"""
    m = m.copy()
    checks = []
    years = sorted(m.ym.dt.year.unique())
    for y in years:
        if y not in ann.index:
            continue
        # 気温（暦年）
        cur = m[m.ym.dt.year == y]
        a_val, a_q = ann.loc[y, "temp_mean"]
        if len(cur) == 12 and cur.temp_mean.notna().all() and a_q in ("正常", "準正常"):
            diff = cur.temp_mean.mean() - a_val
            ok = abs(diff) <= 0.15
            checks.append({"station": station, "year": y, "item": "気温（年平均）", "monthly": round(cur.temp_mean.mean(), 2),
                           "official": a_val, "adopted": ok, "reason": "" if ok else f"年平均気温と {diff:+.2f}℃ ずれる"})
            if not ok:
                m.loc[m.ym.dt.year == y, "temp_mean"] = None
        # 降雪・積雪（寒候年 = 前年8月〜その年7月）
        season = (m.ym >= pd.Timestamp(y - 1, 8, 1)) & (m.ym <= pd.Timestamp(y, 7, 1))
        cur = m[season]
        if len(cur) < 12:
            continue
        for k, label, agg in [("snowfall", "降雪量（寒候年の合計）", "sum"), ("snow_depth_max", "最深積雪（寒候年）", "max")]:
            a_val, a_q = ann.loc[y, k]
            if cur[k].isna().all() and a_val is None:
                continue  # この地点では観測していない
            if a_q not in ("正常", "準正常") or cur[k].isna().any():
                reason = "年ごとの値が資料不足" if a_q == "資料不足" else "月の値に欠損・資料不足がある"
                checks.append({"station": station, "year": y, "item": label, "monthly": cur[k].agg(agg),
                               "official": a_val, "adopted": False, "reason": reason})
                m.loc[season, k] = None
                continue
            val = cur[k].agg(agg)
            ok = abs(val - a_val) < 0.5
            checks.append({"station": station, "year": y, "item": label, "monthly": val, "official": a_val,
                           "adopted": ok, "reason": "" if ok else f"年ごとの値（{a_val:g}cm）と合わない"})
            if not ok:
                m.loc[season, k] = None
    return m, checks


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="start", type=int, default=2009)
    a = p.parse_args()
    this_year = pd.Timestamp.today().year
    stations = pd.read_csv(STATIONS, dtype={"block_no": str, "prec_no": str, "municipality_code": str})
    parts, checks = [], []
    for _, st in stations.iterrows():
        recs = []
        for y in range(a.start, this_year + 1):
            recs += monthly(st, y, refresh=y >= this_year - 1)
        m = pd.DataFrame(recs)
        ann = annual(st, refresh=True)
        m, c = validate(m, ann, st.station)
        checks += c
        bad = [f"{x['year']}{x['item'][:2]}" for x in c if not x["adopted"]]
        print(f"  {st.station}: {m.ym.min():%Y-%m}〜{m.ym.max():%Y-%m} / 照合 {len(c)}件, 除外 {len(bad)}件 {bad}")
        parts.append(m)
    df = pd.concat(parts, ignore_index=True)
    # 品質が「資料不足」の月は使わない
    for k in COLS["s"]:
        df.loc[df[f"{k}_q"].isin(["資料不足", "欠測", "なし"]), k] = None
    df = df[["ym", "station", "temp_mean", "snowfall", "snow_depth_max"]].sort_values(["station", "ym"])
    df = df.dropna(subset=list(COLS["s"]), how="all")  # まだ来ていない月
    OUT.parent.mkdir(parents=True, exist_ok=True)
    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    pd.DataFrame(checks).to_csv(CHECKS, index=False)
    print(f"wrote {OUT} ({len(df):,} rows)")


if __name__ == "__main__":
    main()

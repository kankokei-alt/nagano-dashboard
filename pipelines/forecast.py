"""長野県の客室稼働率（月次）を予測する（ベータ版）。

2つのモデルを作り、過去の年で「当てられたか」を検証して、①より良いときだけ②を採用する。

① 季節パターン … 予測時点の直近12か月の平均稼働率 ＋ 月ごとの季節の山・谷（直近3つの平常年の平均）
② 手がかり入りモデル … ①の予測 ＋ ①からのずれをリッジ回帰で補正。手がかりは
     前年同月が①からどれだけずれていたか、休日数・3連休の回数（その月の例年との差）、
     積雪（スキー場の多い地点, 12〜3月の平年差）、全国の訪日客の伸び×前年の外国人比率、
     大型イベント（config/events.csv）、旅行支援の有無の前年差、新幹線開業から1年、直近3か月の前年差（勢い）

予測時点で分からないもの（先の月の積雪・訪日客）は、実際の予測と同じ条件にそろえる:
  積雪 … 観測済みの月は実績、まだの月は平年並み（その時点までの同じ月の平均）
  訪日客 … 公表済みの月は実績、まだの月は直近3か月の伸びが続くとみなす
  （宿泊旅行統計より気象・JNTO の公表が何か月早いかも、いまの公表状況に合わせる）

検証（ローリング・オリジン）:
  予測時点を1か月ずつ動かし、その時点までのデータだけで学習して 1〜12か月先を予測し、実績と比べる。
  コロナで需要が止まった期間（config/events.csv の kind=covid）にかかる月は、学習にも検証にも使わない。
  「このくらいの幅に収まりそう」は、検証の誤差の 10〜90% 点（先の月ほど広い）。

出力（models/）:
  forecast.parquet  … facility, ym, h, model(採用), pred, lo, hi, seasonal(①), with_clues(②), last_year(前年同月の実績),
                      intercept, c_*（②での手がかりごとの寄与, pt）
  backtest.parquet  … facility, origin, ym, h, actual, seasonal, model
  forecast_meta.json … 採用したモデル、検証の誤差、データの最終月など

使い方:
  python pipelines/forecast.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
OUT = ROOT / "models"
FACILITIES = ["計", "旅館", "リゾートホテル", "ビジネスホテル", "シティホテル"]
SKI = ["白馬", "野沢温泉", "菅平"]
WINTER = [12, 1, 2, 3]
H = 12
SEASON_YEARS = 3  # ①の季節の山・谷に使う年数（直近の平常年）
ALPHA = 10.0  # リッジの強さ（標準化した手がかりに対して）
FEATURES = {  # 列名: 画面での呼び方（いつも使う手がかり）
    "ly_dev": "前年同月", "d_off": "休日数", "d_lw": "3連休", "d_snow": "積雪", "inbound": "訪日客",
    "d_event": "大型イベント", "d_policy": "旅行支援", "struct": "新幹線開業", "mom": "直近の勢い", "mom_h": "直近の勢い",
}
# 全国の暮らし・景気の指標（pipelines/macro.py）。検証で②のずれが小さくなるものだけ自動で採用する
CANDIDATES = {
    "price": "物価の上がり方",          # 消費者物価指数 総合の前年同月比（%）… 実質の負担感
    "hotel_price": "宿泊料の上がり方",   # 宿泊料の前年同月比 − 総合の前年同月比（%）
    "ww_travel": "旅行業界の先行き",     # 景気ウォッチャー 旅行・交通関連の先行き判断DI − 50
    "ww_koshinetsu": "甲信越の景気の先行き",  # 景気ウォッチャー 甲信越の先行き判断DI − 50
    "confidence": "消費者の気持ち",      # 消費者態度指数の前年同月差
}
MIN_GAIN = 0.01  # 採用に必要な、平均のずれの改善幅（pt）


def M(t: pd.Timestamp, k: int) -> pd.Timestamp:
    return t + pd.DateOffset(months=k)


def months_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


# ---------- 入力をそろえる ----------

def load() -> dict:
    s = pd.read_parquet(P / "shukuhaku_monthly.parquet")
    s = s[s.pref_code == "20"]
    occ = s[s.metric == "occupancy"].pivot_table(index="ym", columns="facility", values="value").sort_index()
    g = s[(s.metric.isin(["guests", "foreign"])) & (s.facility == "計")].pivot_table(index="ym", columns="metric", values="value")
    foreign_share = (g.foreign / g.guests).sort_index()

    cal = pd.read_parquet(P / "calendar_monthly.parquet").set_index("month")

    w = pd.read_parquet(P / "weather_monthly.parquet")
    snow = w[w.station.isin(SKI)].pivot_table(index="ym", columns="station", values="snow_depth_max").sort_index()

    macro = pd.read_parquet(P / "macro_monthly.parquet").pivot_table(index="ym", columns="indicator", values="value")

    j = pd.read_parquet(P / "jnto_monthly.parquet")
    jnto = j[j.kind == "total"].set_index("ym").value.sort_index()

    ev = pd.read_csv(ROOT / "config/events.csv", parse_dates=["start", "end"])
    idx = pd.date_range("2009-01-01", "2028-12-01", freq="MS")

    def share(kind: str) -> pd.Series:
        """その月の日数のうち、該当する期間に入っている割合。"""
        out = pd.Series(0.0, index=idx)
        for _, e in ev[ev.kind == kind].iterrows():
            end = e.end if pd.notna(e.end) else e.start
            for m in idx:
                days = pd.date_range(m, M(m, 1) - pd.Timedelta(days=1))
                out[m] = max(out[m], ((days >= e.start) & (days <= end)).mean())
        return out

    struct = pd.Series(0.0, index=idx)
    for _, e in ev[ev.kind == "structural"].iterrows():  # 開業から1年間は前年より押し上げ
        struct[(idx >= e.start.to_period("M").to_timestamp()) & (idx < M(e.start, 12))] = 1.0
    abnormal = share("covid") > 0
    return {"occ": occ, "foreign_share": foreign_share, "cal": cal, "snow": snow, "jnto": jnto, "macro": macro,
            "event": share("event"), "policy": share("policy"), "struct": struct,
            "abnormal": abnormal[abnormal].index}


class Info:
    """予測時点 o で「分かっていること」だけを返す。"""

    def __init__(self, d: dict, o: pd.Timestamp, lags: dict):
        self.d, self.o, self.lags = d, o, lags
        self.snow_known = M(o, lags["weather"])
        self.jnto_known = min(M(o, lags["jnto"]), d["jnto"].index.max())

    def macro(self, ind: str) -> pd.Series:
        """全国の指標のうち、予測時点で公表済みの月まで。"""
        x = self.d["macro"][ind].dropna()
        return x[x.index <= M(self.o, self.lags[ind])]

    def latest(self) -> dict:
        """予測時点で分かっている最新の値（先の月もこの値が続くとみなす）。"""
        yoy = lambda x: (x.iloc[-1] / x.iloc[-13] - 1) * 100  # noqa: E731
        allp, hotel = self.macro("cpi_all"), self.macro("cpi_hotel")
        conf = self.macro("consumer_confidence")
        return {
            "price": yoy(allp),
            "hotel_price": yoy(hotel) - yoy(allp),
            "ww_travel": self.macro("ww_travel_out").iloc[-1] - 50,
            "ww_koshinetsu": self.macro("ww_koshinetsu_out").iloc[-1] - 50,
            "confidence": conf.iloc[-1] - conf.iloc[-13],
        }

    def snow(self, t: pd.Timestamp) -> float:
        """スキー場の多い地点の最深積雪（cm, 地点平均）。まだ観測していない月は平年並み。"""
        sn = self.d["snow"]
        if t <= self.snow_known and t in sn.index and sn.loc[t].notna().any():
            return float(sn.loc[t].mean())
        return self.snow_normal(t)

    def snow_normal(self, t: pd.Timestamp) -> float:
        """平年並み = その時点までに観測した同じ月の平均。"""
        sn = self.d["snow"]
        past = sn[(sn.index.month == t.month) & (sn.index <= self.snow_known)]
        return float(past.mean(axis=1).mean()) if len(past) else 0.0

    def jnto_growth(self, t: pd.Timestamp) -> float:
        """全国の訪日客の前年同月比（対数）。未公表の月は直近3か月の伸びが続くとみなす。"""
        j = self.d["jnto"]
        if t <= self.jnto_known and M(t, -12) in j.index:
            return float(np.log(j[t] / j[M(t, -12)]))
        last = [M(self.jnto_known, -k) for k in range(3)]
        return float(np.log(sum(j[m] for m in last) / sum(j[M(m, -12)] for m in last)))


def features(d: dict, occ: pd.Series, info: Info, t: pd.Timestamp, base1: float) -> dict:
    """①の予測からのずれを説明する手がかり。休日・積雪は「その月の例年」との差。"""
    o, ly = info.o, M(t, -12)
    cal = d["cal"]
    same = cal[(cal.index.month == t.month) & (cal.index.year.isin(range(2011, 2026)))]
    mom = np.mean([occ[M(o, -k)] - occ[M(o, -k - 12)] for k in range(3)])
    h = months_between(o, t)
    fs = d["foreign_share"]
    return {
        **info.latest(),
        "ly_dev": occ[ly] - base1,
        "d_off": cal.off_days[t] - same.off_days.mean(),
        "d_lw": cal.long_weekends[t] - same.long_weekends.mean(),
        "d_snow": (info.snow(t) - info.snow_normal(t)) if t.month in WINTER else 0.0,
        "inbound": info.jnto_growth(t) * fs.get(ly, np.nan) * 100,  # 前年の外国人比率で重みづけ（%）
        "d_event": d["event"][t],
        "d_policy": d["policy"][t] - d["policy"][ly],
        "struct": d["struct"][t],
        "mom": mom,
        "mom_h": mom * (h - 1) / (H - 1),  # 先の月ほど勢いは弱まる（係数で学習）
    }


def is_normal(d: dict, months) -> bool:
    return not any(m in d["abnormal"] for m in months)


# ---------- モデル ----------

def seasonal(occ: pd.Series, d: dict, o: pd.Timestamp, t: pd.Timestamp) -> float:
    """① 直近12か月の平均 ＋ 月ごとの季節の山・谷（o までに終わった平常年のうち直近3年の平均）。

    夏の山は 2010年代より小さくなっているので、古い年まで平均すると8月を高く見すぎる。"""
    level = occ[M(o, -11):o].mean()
    hist = occ[:o]
    years = [y for y in sorted(set(hist.index.year))
             if (hist.index.year == y).sum() == 12 and is_normal(d, hist[hist.index.year == y].index)][-SEASON_YEARS:]
    dev = pd.concat([hist[hist.index.year == y] - hist[hist.index.year == y].mean() for y in years])
    return level + dev[dev.index.month == t.month].mean()


def ridge_fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    b = np.linalg.solve(Z.T @ Z + ALPHA * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    coef = b / sd
    return coef, y.mean() - mu @ coef, mu, sd


def rows(d: dict, occ: pd.Series, origins, last: pd.Timestamp, lags: dict) -> pd.DataFrame:
    """(予測時点 o, 対象月 t) の組ごとの手がかりと答え。"""
    out = []
    for o in origins:
        if not is_normal(d, [M(o, -k) for k in range(15)]) or M(o, -14) < occ.index.min():
            continue  # 直近の水準・勢いがコロナ期間にかかる時点は使わない
        info = Info(d, o, lags)
        for h in range(1, H + 1):
            t = M(o, h)
            if t > M(last, H) or not is_normal(d, [t, M(t, -12)]):
                continue
            base1 = seasonal(occ, d, o, t)
            f = features(d, occ, info, t, base1)
            f.update(origin=o, ym=t, h=h, base=base1, ly=occ[M(t, -12)],
                     actual=occ.get(t, np.nan) if t <= last else np.nan)
            out.append(f)
    return pd.DataFrame(out)


def backtest(allrows: pd.DataFrame, cols: list[str], last: pd.Timestamp, facility: str) -> pd.DataFrame:
    """予測時点ごとに、それまでに答えが分かっている組だけで学習して 1〜12か月先を予測する。"""
    bt = []
    for o in [o for o in allrows.origin.unique() if pd.Timestamp("2015-01-01") <= o < last]:
        train = allrows[(allrows.ym <= o) & allrows.actual.notna()]
        test = allrows[(allrows.origin == o) & (allrows.ym <= last)]
        if len(train) < 60 or test.empty:
            continue
        coef, c0, _, _ = ridge_fit(train[cols].values, (train.actual - train.base).values)
        pred = test.base.values + c0 + test[cols].values @ coef
        bt.append(pd.DataFrame({"facility": facility, "origin": o, "ym": test.ym.values, "h": test.h.values,
                                "actual": test.actual.values, "seasonal": test.base.values, "model": pred}))
    return pd.concat(bt, ignore_index=True)


def mae(bt: pd.DataFrame, k: str) -> float:
    return float((bt[k] - bt.actual).abs().mean())


def prepare(d: dict, facility: str, lags: dict) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    occ = d["occ"][facility].dropna()
    last = occ.index.max()
    allrows = rows(d, occ, pd.date_range(occ.index.min(), last, freq="MS"), last, lags)
    allrows = allrows[allrows.inbound.notna()]
    return occ, allrows, rows(d, occ, [last], last, lags)


def select(prepared: dict) -> tuple[list[str], list[dict]]:
    """全国の指標を1つずつ足して、5系列の②の平均のずれが MIN_GAIN 以上小さくなるものだけ採用する（前向き選択）。"""
    def score(cols):
        return np.mean([mae(backtest(a, cols, occ.index.max(), f), "model") for f, (occ, a, _) in prepared.items()])

    chosen, base = [], score(list(FEATURES))
    log = [{"step": 0, "added": "（いつも使う手がかりだけ）", "mae": base}]
    while True:
        rest = [c for c in CANDIDATES if c not in chosen]
        trials = {c: score(list(FEATURES) + chosen + [c]) for c in rest}
        for c, v in trials.items():
            log.append({"step": len(chosen) + 1, "added": CANDIDATES[c], "mae": v, "gain": base - v})
        if not trials:
            break
        best = min(trials, key=trials.get)
        if base - trials[best] < MIN_GAIN:
            break
        chosen.append(best)
        base = trials[best]
    return chosen, log


def run(facility: str, occ: pd.Series, allrows: pd.DataFrame, now: pd.DataFrame, cols: list[str]
        ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    last = occ.index.max()
    names = {**FEATURES, **CANDIDATES}
    bt = backtest(allrows, cols, last, facility)
    err_ = {k: mae(bt, k) for k in ["seasonal", "model"]}
    chosen = "model" if err_["model"] < err_["seasonal"] else "seasonal"

    # いまの予測（全データで学習）
    train = allrows[allrows.actual.notna()]
    coef, c0, _, _ = ridge_fit(train[cols].values, (train.actual - train.base).values)
    err = bt.assign(e=bt.actual - bt[chosen])
    fc = []
    for _, r in now.iterrows():
        e = err[err.h.between(*((1, 3) if r.h <= 3 else (4, 6) if r.h <= 6 else (7, 12)))].e
        contrib = {names[k]: 0.0 for k in cols}
        for k, cf in zip(cols, coef):
            contrib[names[k]] += cf * r[k]
        p_model = r.base + c0 + sum(contrib.values())
        p_seas = r.base
        pred = p_model if chosen == "model" else p_seas
        fc.append({"facility": facility, "ym": r.ym, "h": r.h, "model": chosen, "pred": pred,
                   "lo": pred + e.quantile(0.1), "hi": pred + e.quantile(0.9),
                   "seasonal": p_seas, "with_clues": p_model, "last_year": r.ly, "intercept": c0,
                   **{f"c_{k}": v for k, v in contrib.items()}})
    by_h = (bt.assign(seasonal=(bt.seasonal - bt.actual).abs(), model=(bt.model - bt.actual).abs())
              .assign(hb=lambda x: pd.cut(x.h, [0, 3, 6, 12], labels=["1〜3か月先", "4〜6か月先", "7〜12か月先"]))
              .groupby("hb", observed=True)[["seasonal", "model"]].mean().round(2).to_dict("index"))
    meta = {"facility": facility, "last_actual": f"{last:%Y-%m}", "chosen": chosen, "mae": err_, "mae_by_h": by_h,
            "n_backtest": int(len(bt)), "n_origins": int(bt.origin.nunique()),
            "backtest_years": sorted({int(y) for y in bt.ym.dt.year}),
            "coef": {k: float(v) for k, v in zip(cols, coef)},
            "latest_inputs": {names[k]: float(now[k].iloc[0]) for k in cols if k in CANDIDATES}}
    return pd.DataFrame(fc), bt, meta


def main() -> None:
    d = load()
    occ_last = d["occ"]["計"].dropna().index.max()
    lags = {"weather": months_between(occ_last, d["snow"].dropna(how="all").index.max()),
            "jnto": months_between(occ_last, d["jnto"].index.max()),
            **{k: months_between(occ_last, d["macro"][k].dropna().index.max()) for k in d["macro"].columns}}
    print(f"宿泊旅行統計 {occ_last:%Y-%m} まで / ほかの指標が何か月先まで公表済みか: {lags}")
    prepared = {f: prepare(d, f, lags) for f in FACILITIES}

    extra, log = select(prepared)
    for x in log:
        print(f"  [{x['step']}] {x['added']}: 5系列の②の平均のずれ {x['mae']:.3f}pt" + (f"（{x['gain']:+.3f}）" if "gain" in x else ""))
    print(f"  → 採用した全国の指標: {[CANDIDATES[c] for c in extra] or 'なし'}")
    cols = list(FEATURES) + extra

    fcs, bts, metas = [], [], []
    for f, (occ, allrows, now) in prepared.items():
        fc, bt, meta = run(f, occ, allrows, now, cols)
        fcs.append(fc), bts.append(bt), metas.append(meta)
        print(f"  {f}: ① {meta['mae']['seasonal']:.2f}pt / ② {meta['mae']['model']:.2f}pt → "
              f"{'②' if meta['chosen'] == 'model' else '①'}を採用（検証 {meta['n_backtest']}件）")
    OUT.mkdir(exist_ok=True)
    pd.concat(fcs).to_parquet(OUT / "forecast.parquet", index=False)
    pd.concat(bts).to_parquet(OUT / "backtest.parquet", index=False)
    (OUT / "forecast_meta.json").write_text(json.dumps(
        {"generated": f"{pd.Timestamp.today():%Y-%m-%d}", "lag_weather": lags["weather"], "lag_jnto": lags["jnto"],
         "lags": lags, "snow_stations": SKI, "candidates": CANDIDATES, "selected": [CANDIDATES[c] for c in extra],
         "selection_log": log, "facilities": metas}, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"wrote {OUT}/forecast.parquet, backtest.parquet, forecast_meta.json")


if __name__ == "__main__":
    main()

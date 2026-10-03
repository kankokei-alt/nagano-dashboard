import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui

ui.setup("稼働率予測（ベータ版）", "長野県の客室稼働率が、この先12か月どうなりそうかを月ごとに予測するページです（試作中）。")

meta = data.forecast_meta()
fc_all = data.forecast()
bt_all = data.backtest()
occ = data.shukuhaku_occupancy()
NAMES = {"計": "全体", "旅館": "旅館", "リゾートホテル": "リゾートホテル", "ビジネスホテル": "ビジネスホテル", "シティホテル": "シティホテル"}
MODEL_NAME = {"seasonal": "① 季節パターン", "model": "② 手がかり入りモデル"}


def ym(t: pd.Timestamp) -> str:
    return f"{t.year}年{t.month}月"


fac = st.radio("宿の種類", list(NAMES), format_func=NAMES.get, horizontal=True)
m = next(x for x in meta["facilities"] if x["facility"] == fac)
fc = fc_all[fc_all.facility == fac].sort_values("ym")
bt = bt_all[bt_all.facility == fac]
hist = occ[fac].dropna()
last = hist.index.max()
chosen = m["chosen"]
other = "seasonal" if chosen == "model" else "model"
nxt = fc.iloc[0]
diff = fc.pred - fc.last_year
up, down = fc.loc[diff.idxmax()], fc.loc[diff.idxmin()]

# ---- ここがポイント（すべて予測結果から組み立てる） ----
def vs_ly(r) -> str:
    d = r.pred - r.last_year
    return "前年並み" if abs(d) < 0.5 else f"前年より {abs(d):.1f}ポイント{'高く' if d > 0 else '低く'}"


text = (
    f"{NAMES[fac]}の客室稼働率は、<b>{ym(nxt.ym)}は {nxt.pred:.0f}% 前後</b>"
    f"（{nxt.lo:.0f}〜{nxt.hi:.0f}% の幅）で、{vs_ly(nxt)}なりそうです。"
)
if diff.max() >= 0.5:
    text += f"<br>今後12か月で前年をいちばん上回りそうなのは <b>{ym(up.ym)}</b>（{up.pred:.0f}%, {vs_ly(up)}）"
    text += (f"、いちばん下回りそうなのは <b>{ym(down.ym)}</b>（{down.pred:.0f}%, {vs_ly(down)}）です。"
             if diff.min() <= -0.5 else "で、前年を大きく下回りそうな月はありません。")
else:
    text += (f"<br>今後12か月はおおむね前年並みか下回る見込みで、いちばん下回りそうなのは <b>{ym(down.ym)}</b>"
             f"（{down.pred:.0f}%, {vs_ly(down)}）です。")
text += (f"<br><small>予測には過去の検証で誤差の小さかった <b>{MODEL_NAME[chosen]}</b> を使っています"
         f"（平均のずれ {m['mae'][chosen]:.1f}ポイント。{MODEL_NAME[other]}は {m['mae'][other]:.1f}ポイント）。</small>")
ui.insight(text)

st.warning(
    f"ベータ版です。{ym(last)}までの宿泊旅行統計で学習しています。"
    + (f"{last.year}年1月分から調査の区分け（層化基準）が変わったため、前年との比較には見直しの影響が含まれることがあります。"
       if last.year >= 2026 else ""),
    icon="🧪",
)

cols = st.columns(3)
with cols[0]:
    ui.kpi(f"{ym(nxt.ym)}の予測", f"{nxt.pred:.1f}%", f"幅 {nxt.lo:.0f}〜{nxt.hi:.0f}%／前年同月 {nxt.last_year:.1f}%")
q = fc.head(3)
with cols[1]:
    ui.kpi(f"今後3か月の平均（{q.ym.iloc[0].month}〜{q.ym.iloc[-1].month}月）", f"{q.pred.mean():.1f}%",
           f"前年同期 {q.last_year.mean():.1f}%（{q.pred.mean() - q.last_year.mean():+.1f}pt）")
with cols[2]:
    ui.kpi("予測のずれ（過去の検証）", f"±{m['mae'][chosen]:.1f}pt",
           f"{m['n_origins']}回の予測で、1〜12か月先を平均して")

# ---- 予測のグラフ ----
st.subheader("これまでの実績と、この先12か月の予測")
since = last - pd.DateOffset(months=23)
h = hist[hist.index >= since]
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=list(fc.ym) + list(fc.ym[::-1]), y=list(fc.hi) + list(fc.lo[::-1]), fill="toself",
    fillcolor="rgba(42,120,214,.15)", line={"width": 0}, name="このくらいの幅に収まりそう", hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=fc.ym, y=fc.last_year, name="前年同月の実績", mode="lines",
    line={"color": charts.CONTEXT, "width": 2, "dash": "dot"},
    hovertemplate="前年同月 %{y:.1f}%<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=h.index, y=h.values, name="実績", mode="lines+markers",
    line={"color": charts.MAIN, "width": 3}, marker={"size": 6},
    hovertemplate="%{x|%Y年%-m月} 実績 %{y:.1f}%<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=[h.index[-1]] + list(fc.ym), y=[h.iloc[-1]] + list(fc.pred), name="予測", mode="lines+markers",
    line={"color": charts.MAIN, "width": 2, "dash": "dash"}, marker={"size": 8, "symbol": "circle-open"},
    customdata=[["", ""]] + [[f"{a:.0f}", f"{b:.0f}"] for a, b in zip(fc.lo, fc.hi)],
    hovertemplate="%{x|%Y年%-m月} 予測 %{y:.1f}%（%{customdata[0]}〜%{customdata[1]}%）<extra></extra>",
))
fig.add_vline(x=last + pd.Timedelta(days=15), line={"color": "rgba(128,128,128,.5)", "width": 1})
fig.add_annotation(x=last + pd.Timedelta(days=15), y=1, yref="paper", text="ここから予測", showarrow=False,
                   xanchor="left", xshift=6, font={"size": 12})
charts.layout(fig, height=400, hovermode="x unified")
fig.update_yaxes(title="客室稼働率（%）", ticksuffix="%", rangemode="tozero")
fig.update_xaxes(tickformat="%Y年<br>%-m月", dtick="M3")
st.plotly_chart(fig, use_container_width=True)
st.caption("帯は「過去の検証で、10回のうち8回は実績がこの幅に収まった」範囲です。先の月ほど幅が広くなります。"
           "出典: 観光庁「宿泊旅行統計調査」をもとに作成")

with st.expander("月ごとの予測の数字"):
    tbl = pd.DataFrame({
        "月": fc.ym.map(ym), "予測（%）": fc.pred.round(1),
        "幅（%）": [f"{a:.0f}〜{b:.0f}" for a, b in zip(fc.lo, fc.hi)],
        "前年同月（%）": fc.last_year.round(1), "前年との差（pt）": (fc.pred - fc.last_year).round(1),
    })
    st.dataframe(tbl, hide_index=True, use_container_width=True)

# ---- 何が効いているか ----
st.subheader("予測の手がかり")
clue_cols = [c for c in fc.columns if c.startswith("c_")]
contrib = fc.set_index("ym")[clue_cols].rename(columns=lambda c: c[2:])
total = contrib.abs().sum().sort_values(ascending=False)
if chosen == "model":
    st.markdown("②のモデルは、①の季節パターンを出発点に、下の手がかりで上下に補正しています。"
                "棒が右なら稼働率を押し上げ、左なら押し下げる方向に働いています。")
else:
    st.markdown(f"{NAMES[fac]}では、手がかりを加えた②のほうが過去の検証でずれが大きかったため、"
                "予測には①（季節パターン）を使っています。参考として、②が手がかりをどう見ているかを示します。")
mon = st.select_slider("月を選ぶ", options=list(fc.ym), format_func=ym, value=fc.ym.iloc[0])
c = contrib.loc[mon]
c = c[c.abs() >= 0.05].sort_values()
c1, c2 = st.columns([3, 2])
with c1:
    if c.empty:
        st.info("この月は、①の季節パターンから大きく動かす手がかりがありません。")
    else:
        fig = go.Figure(go.Bar(
            y=c.index, x=c.values, orientation="h",
            marker_color=[charts.MAIN if v > 0 else charts.SECOND for v in c.values],
            text=[f"{v:+.1f}pt" for v in c.values], textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b> %{x:+.2f}ポイント<extra></extra>",
        ))
        lim = max(c.abs().max() * 1.4, 1)
        charts.layout(fig, height=60 + 40 * len(c))
        fig.update_xaxes(range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)", ticksuffix="pt")
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(fig, use_container_width=True)
with c2:
    r = fc.set_index("ym").loc[mon]
    lines = [f"- ①季節パターン: **{r.seasonal:.1f}%**", f"- ②手がかり入り: **{r.with_clues:.1f}%**"]
    if not c.empty:
        lines.append(f"- いちばん大きいのは **{c.abs().idxmax()}**（{c[c.abs().idxmax()]:+.1f}pt）")
    st.markdown("\n".join(lines))
    st.caption("「前年同月」は、前年の同じ月が季節パターンより高かった（低かった）分を一部引き継ぐ効果です。"
               "まだ観測していない月の積雪は平年並み、まだ公表されていない月の訪日客は直近3か月の伸びが続くとみなしています。")

# ---- 当たったか ----
st.subheader("過去の年で、当てられたか")
e = bt.assign(**{k: (bt[k] - bt.actual).abs() for k in ["seasonal", "model"]})
e["区分"] = pd.cut(e.h, [0, 3, 6, 12], labels=["1〜3か月先", "4〜6か月先", "7〜12か月先"])
g = e.groupby("区分", observed=True)[["seasonal", "model"]].mean()
c1, c2 = st.columns([3, 2])
with c1:
    fig = go.Figure()
    for k, color in [("seasonal", charts.CONTEXT), ("model", charts.SECOND)]:
        name = MODEL_NAME[k] + ("（採用）" if k == chosen else "")
        fig.add_trace(go.Bar(
            x=g.index.astype(str), y=g[k], name=name, marker_color=color if k != chosen else charts.MAIN,
            marker_line={"color": "white", "width": 2}, text=[f"{v:.1f}" for v in g[k]], textposition="outside",
            hovertemplate=f"{name}<br>%{{x}}: 平均のずれ %{{y:.2f}}ポイント<extra></extra>",
        ))
    charts.layout(fig, height=300, barmode="group", bargap=0.3)
    fig.update_yaxes(title="予測と実績の平均のずれ（pt）", rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True)
with c2:
    yrs = m["backtest_years"]
    pre = [y for y in yrs if y <= 2020]
    post = [y for y in yrs if y > 2020]
    better = (g.model < g.seasonal)
    st.markdown(
        f"予測する時点を1か月ずつずらしながら、その時点までのデータだけで1〜12か月先を予測し、実績と比べました"
        f"（{m['n_origins']}回・{m['n_backtest']:,}件）。"
        f"コロナで需要が止まった期間は検証から外しています。\n\n"
        + (f"②は **{'・'.join(g.index[better].astype(str))}** で①よりずれが小さく、"
           if better.any() else "②はどの先の月でも①よりずれが小さくなりませんでした。")
        + f"全体では{MODEL_NAME[chosen]}のほうが当たっていたので、こちらを採用しています。"
    )
    st.caption(f"検証した年: {pre[0]}〜{pre[-1]}年" + (f"、{post[0]}〜{post[-1]}年" if post else "")
               + "。ずれは稼働率のポイント（例: 40% と予測して 42% なら 2ポイント）。")

# ---- 雪の状況 ----
st.subheader("雪の状況（スキー場の多い地点）")
wx = data.weather()
ski = wx[wx.station.isin(meta["snow_stations"])].copy()
ski["season"] = ski.ym.dt.year + (ski.ym.dt.month >= 8)  # 寒候年（8月〜翌7月）
peak = ski.groupby(["station", "season"]).snow_depth_max.max().unstack(0)
# 12〜3月がそろっている冬だけ（取り込みの最初の冬は途中からなので外す）
done_seasons = [y for y in peak.index
                if pd.Timestamp(y - 1, 12, 1) >= wx.ym.min() and pd.Timestamp(y, 3, 1) <= wx.ym.max()]
ls = max(done_seasons)
normal = peak.loc[[y for y in done_seasons if y < ls]].mean()
ratio = (peak.loc[ls] / normal).dropna()
fig = go.Figure()
for i, (stn, v) in enumerate(peak.loc[done_seasons].items()):
    fig.add_trace(go.Scatter(
        x=[f"{y - 1}〜{y % 100:02d}年" for y in v.index], y=v.values, name=stn, mode="lines+markers",
        line={"color": [charts.MAIN, charts.SECOND, charts.THIRD][i], "width": 2}, marker={"size": 7},
        hovertemplate=f"{stn} %{{x}}の冬 最深積雪 %{{y:.0f}}cm<extra></extra>",
    ))
charts.layout(fig, height=300, hovermode="x unified")
fig.update_yaxes(title="その冬の最深積雪（cm）", rangemode="tozero")
fig.update_xaxes(type="category", dtick=2)
c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(fig, use_container_width=True)
with c2:
    lo_st, hi_st = ratio.idxmin(), ratio.idxmax()
    st.markdown(
        f"{ls - 1}〜{str(ls)[2:]}年の冬の最深積雪は、{'・'.join(f'{k} {peak.loc[ls, k]:.0f}cm' for k in ratio.index)}。"
        f"それまでの冬の平均と比べると **{lo_st}** が{ratio[lo_st]:.0%}、**{hi_st}** が{ratio[hi_st]:.0%}でした。\n\n"
        "まだ観測していない冬の積雪は分からないので、予測では「平年並み」として扱っています。"
    )
    st.caption("出典: 気象庁「過去の気象データ」。年ごとの値が資料不足の冬は表示していません。")

# ---- カレンダー要因 ----
with st.expander("カレンダーから見た追い風・向かい風（休日数）"):
    cal = data.calendar_monthly()
    cal["month"] = pd.to_datetime(cal.month)
    cal["m"] = cal.month.dt.month
    base = cal[(cal.month >= "2015-01-01") & (cal.month < "2026-01-01")].groupby("m").off_days.mean()
    ahead = cal[cal.month.isin(fc.ym)].copy()
    ahead["diff"] = ahead.off_days - ahead.m.map(base)
    ahead["label"] = ahead.month.map(ym)
    best = ahead.sort_values(["diff", "long_weekends"], ascending=False).iloc[0]
    worst = ahead.sort_values(["diff", "long_weekends"]).iloc[0]
    st.markdown(
        f"予測する12か月では **{best.label}** が例年より休みが {best['diff']:+.1f} 日（3連休以上 {int(best.long_weekends)} 回）、"
        f"**{worst.label}** は {worst['diff']:+.1f} 日です。"
    )
    fig = go.Figure(go.Bar(
        x=ahead.label, y=ahead["diff"], marker_line_width=0,
        marker_color=[charts.MAIN if d > 0.5 else charts.SECOND if d < -0.5 else charts.CONTEXT for d in ahead["diff"]],
        customdata=ahead[["off_days", "long_weekends", "max_off_run"]].values,
        hovertemplate="<b>%{x}</b><br>例年との差 %{y:+.1f} 日<br>休日 %{customdata[0]} 日"
        "／3連休以上 %{customdata[1]} 回／最長 %{customdata[2]} 連休<extra></extra>",
    ))
    charts.layout(fig, height=300)
    fig.update_yaxes(title="例年（2015〜2025年平均）との差（日）", zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("青＝例年より休みが多い月、オレンジ＝少ない月。土日・祝日・年末年始（12/29〜1/3）を休日として数えています。")

with st.expander("予測のしくみ"):
    rows = "\n".join(
        f"| {NAMES[x['facility']]} | {x['mae']['seasonal']:.2f} | {x['mae']['model']:.2f} | {MODEL_NAME[x['chosen']]} |"
        for x in meta["facilities"]
    )
    st.markdown(
        f"""
- **予測するもの**: 長野県の客室稼働率（月次、宿の種類別）… 観光庁「宿泊旅行統計調査」
- **① 季節パターン**: 直近12か月の平均稼働率に、月ごとの季節の山・谷（コロナ期間を除く過去の年の平均）を足したもの
- **② 手がかり入りモデル**: ①を出発点に、前年同月のずれ、休日数・3連休の回数、積雪（{'・'.join(meta['snow_stations'])}）、
  全国の訪日客の伸び（JNTO）、大型イベント・旅行支援・新幹線開業（config/events.csv）、直近3か月の勢いで補正（リッジ回帰）
- **公平な検証**: 予測する時点で分からないこと（先の月の積雪・まだ公表されていない訪日客）は、検証でも使わないようにしています。
  いまは宿泊旅行統計より気象が{meta['lag_weather']}か月、JNTO が{meta['lag_jnto']}か月先まで公表済みです
- **採用のルール**: 過去の検証で①より平均のずれが小さいときだけ②を使います

| 宿の種類 | ①のずれ（pt） | ②のずれ（pt） | 採用 |
|---|---|---|---|
{rows}

作成日: {meta['generated']}（`python pipelines/forecast.py` で作り直せます）
"""
    )

ui.sources(["shukuhaku", "holidays", "events", "weather", "jnto"])

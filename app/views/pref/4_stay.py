import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib import charts, data, ui

ui.setup("宿と稼働率", "部屋がどのくらい埋まっているか（客室稼働率）を宿の種類・月ごとに。")

occ = data.shukuhaku_occupancy("20")
nat = data.shukuhaku_occupancy("00")
last = occ.index.max()
fy = last.year - 1
TYPES = ["旅館", "リゾートホテル", "ビジネスホテル", "シティホテル", "簡易宿所", "会社・団体の宿泊所"]
recent = occ.loc[last - pd.DateOffset(months=11):last].mean()
recent_nat = nat.loc[last - pd.DateOffset(months=11):last].mean()
y19 = occ[occ.index.year == 2019].mean()
ym = f"{last.year}年{last.month}月"

rt = recent.reindex(TYPES).dropna().sort_values(ascending=False)
gap_now = recent["計"] - recent_nat["計"]
ui.insight(
    f"{ym}までの1年間の長野県の客室稼働率は平均 <b>{recent['計']:.1f}%</b> で、全国（{recent_nat['計']:.1f}%）より "
    f"{abs(gap_now):.1f}ポイント{'低く' if gap_now < 0 else '高く'}なっています。"
    f"宿の種類で見ると、{rt.index[0]}（{rt.iloc[0]:.0f}%）・{rt.index[1]}（{rt.iloc[1]:.0f}%）が高く、"
    f"{rt.index[-2]}（{rt.iloc[-2]:.0f}%）・{rt.index[-1]}（{rt.iloc[-1]:.0f}%）が低くなっています。"
)
st.caption("客室稼働率 ＝ 実際に使われた部屋の数 ÷ 泊まれる部屋の数。観光庁「宿泊旅行統計調査」の数字です。")

# ---- 1. 推移 ----
ui.block("📈 客室稼働率の推移", "長野県と全国、直近12か月の平均")
r20 = occ["計"].rolling(12).mean().dropna()
r00 = nat["計"].rolling(12).mean().dropna()
fig = go.Figure()
for v, label, color in [(r00, "全国", charts.CONTEXT), (r20, "長野県", charts.MAIN)]:
    fig.add_trace(go.Scatter(x=v.index, y=v, name=label, mode="lines", line={"color": color, "width": 3 if label == "長野県" else 2},
                             hovertemplate=f"{label} %{{x|%Y年%-m月}}までの1年間 %{{y:.1f}}%<extra></extra>"))
    fig.add_annotation(x=v.index[-1], y=v.iloc[-1], text=f"<b>{label}</b>", showarrow=False, xanchor="left", xshift=6)
charts.layout(fig, height=330, hovermode="x unified")
fig.update_yaxes(title="客室稼働率（直近12か月の平均, %）", ticksuffix="%", rangemode="tozero")
st.plotly_chart(fig, use_container_width=True)
gap = r00 - r20
ui.readout([
    f"いま（{ym}までの1年間）の差は **{gap.iloc[-1]:.1f}ポイント**。コロナ前（2019年12月までの1年間）の差は {gap[pd.Timestamp(2019, 12, 1)]:.1f}ポイントでした。",
    f"長野県の稼働率は、2019年の平均（{y19['計']:.1f}%）に対して {recent['計'] - y19['計']:+.1f}ポイントです。",
], source="観光庁「宿泊旅行統計調査」" + ("（今年は速報値）" if last.year >= 2026 else ""))

# ---- 2. 宿の種類別 ----
ui.block("🏨 タイプ別の稼働率（全国比較）", "直近12か月の平均。全体の稼働率はタイプの構成に左右されます")
t = pd.DataFrame({"長野県": recent.reindex(TYPES), "全国": recent_nat.reindex(TYPES)}).dropna()
fig = go.Figure()
for col, color in [("長野県", charts.MAIN), ("全国", charts.CONTEXT)]:
    fig.add_trace(go.Bar(x=t.index, y=t[col], name=col, marker_color=color,
                         marker_line={"color": "white", "width": 2}, text=[f"{v:.0f}%" for v in t[col]], textposition="outside",
                         hovertemplate=f"%{{x}} {col} %{{y:.1f}}%<extra></extra>"))
charts.layout(fig, height=340, barmode="group", bargap=0.3)
fig.update_yaxes(title="客室稼働率（%）", ticksuffix="%", range=[0, t.values.max() * 1.18])
st.plotly_chart(fig, use_container_width=True)
gap_t = (t["長野県"] - t["全国"]).sort_values()
dd = (recent.reindex(TYPES) - y19.reindex(TYPES)).dropna()
ui.readout([
    f"全体（全タイプ合計）では全国より **{abs(gap_now):.1f}ポイント{'低い' if gap_now < 0 else '高い'}** ですが、"
    f"タイプ別に見ると差は {gap_t.min():+.1f}〜{gap_t.max():+.1f}ポイントです。",
    (f"全国より高いのは **{'・'.join(gap_t[gap_t > 0.5].index)}**、" if (gap_t > 0.5).any() else "")
    + f"差がいちばん大きいのは **{gap_t.index[0]}**（{gap_t.iloc[0]:+.1f}ポイント）です。",
    f"2019年と比べて上がったのは {'・'.join(dd[dd > 0.5].index) or 'なし'}、下がったのは {'・'.join(dd[dd < -0.5].index) or 'なし'} です。",
], source="観光庁「宿泊旅行統計調査」（直近12か月の平均）")

# ---- 3. 種類×月 ----
ui.block("🗓️ タイプ別・月別の稼働率", "色が濃いほど高い")
hm = occ[occ.index.year == fy][[c for c in TYPES if c in occ.columns]].T
hm.columns = [f"{m}月" for m in hm.columns.month]
fig = go.Figure(go.Heatmap(
    z=hm.values, x=hm.columns, y=hm.index, colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]],
    zmin=0, zmax=100, text=[[f"{v:.0f}" for v in r] for r in hm.values], texttemplate="%{text}", xgap=2, ygap=2,
    hovertemplate="%{y} %{x}: %{z:.1f}%<extra></extra>", colorbar={"title": "稼働率（%）"},
))
charts.layout(fig, height=320)
fig.update_xaxes(side="top")
fig.update_yaxes(showgrid=False, autorange="reversed")
st.plotly_chart(fig, use_container_width=True)
spread = (hm.max(axis=1) - hm.min(axis=1)).sort_values()
lowm = hm.idxmin(axis=1)
ui.readout([
    f"季節による差がいちばん大きいのは **{spread.index[-1]}**（最も高い月と低い月で {spread.iloc[-1]:.0f}ポイント）、"
    f"小さいのは **{spread.index[0]}**（{spread.iloc[0]:.0f}ポイント）です。",
    "それぞれいちばん空きが出やすい月: " + "、".join(f"{k} {v}" for k, v in lowm.items()) + "。",
], source=f"観光庁「宿泊旅行統計調査」（{fy}年）")

# ---- 4. 全国との差 ----
ui.block("📈 タイプ別の推移（全国比較）", "直近12か月の平均")
types = [c for c in TYPES if c in occ.columns and c in nat.columns]
r20 = occ[types].rolling(12).mean()
r00 = nat[types].rolling(12).mean()
since = pd.Timestamp(2015, 12, 1)
fig = make_subplots(rows=2, cols=3, subplot_titles=types, shared_xaxes=True, vertical_spacing=0.14)
for i, c in enumerate(types):
    for v, label, color, width in [(r00[c], "全国", charts.CONTEXT, 1.5), (r20[c], "長野県", charts.MAIN, 2.5)]:
        v = v[v.index >= since].dropna()
        fig.add_trace(go.Scatter(x=v.index, y=v, name=label, mode="lines", line={"color": color, "width": width},
                                 showlegend=(i == 0), legendgroup=label,
                                 hovertemplate=f"{c} {label} %{{x|%Y年%-m月}}までの1年間 %{{y:.1f}}%<extra></extra>"),
                      row=i // 3 + 1, col=i % 3 + 1)
charts.layout(fig, height=480, legend_below=True)
fig.update_yaxes(ticksuffix="%", rangemode="tozero")
st.plotly_chart(fig, use_container_width=True)
g_now = (r20.iloc[-1] - r00.iloc[-1])
g_19 = (r20.loc[pd.Timestamp(2019, 12, 1)] - r00.loc[pd.Timestamp(2019, 12, 1)])
chg = (g_now - g_19).dropna().sort_values()
ui.readout([
    "いまの全国との差: " + "、".join(f"{k} {v:+.1f}pt" for k, v in g_now.items()) + "。",
    f"2019年と比べて全国との差が縮まった（長野県が追い上げた）のは **{'・'.join(chg[chg > 0.5].index[::-1]) or 'なし'}**、"
    f"広がったのは **{'・'.join(chg[chg < -0.5].index) or 'なし'}** です。",
], source="観光庁「宿泊旅行統計調査」")

ui.sources(["shukuhaku"])

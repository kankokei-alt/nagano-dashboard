import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui

ui.setup("宿と稼働率", "長野県のホテル・旅館の部屋がどのくらい埋まっているか（客室稼働率）を、宿の種類ごと・月ごとに見るページです。")

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
ui.block("📈 客室稼働率の移り変わり（長野県と全国）",
         "長野県と全国の客室稼働率を、季節の波をならすために直近12か月の平均で比べたもの",
         "長野県の宿の埋まり具合が、全国と比べて回復しているか、差が縮まっているかを知りたいとき")
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
ui.block("🏨 宿の種類ごとの稼働率",
         "旅館・リゾートホテル・ビジネスホテルなど、宿の種類ごとの客室稼働率（直近12か月の平均）を、コロナ前（2019年）と比べたもの",
         "自分の地域の宿の種類と比べて、県全体の傾向を知りたいとき")
t = pd.DataFrame({"2019年": y19.reindex(TYPES), "直近12か月": recent.reindex(TYPES)}).dropna()
fig = go.Figure()
for col, color in [("2019年", charts.CONTEXT), ("直近12か月", charts.MAIN)]:
    fig.add_trace(go.Bar(x=t.index, y=t[col], name=col if col != "2019年" else "2019年（コロナ前）", marker_color=color,
                         marker_line={"color": "white", "width": 2}, text=[f"{v:.0f}%" for v in t[col]], textposition="outside",
                         hovertemplate=f"%{{x}} {col} %{{y:.1f}}%<extra></extra>"))
charts.layout(fig, height=330, barmode="group", bargap=0.3)
fig.update_yaxes(title="客室稼働率（%）", ticksuffix="%", range=[0, t.values.max() * 1.18])
st.plotly_chart(fig, use_container_width=True)
dd = (t["直近12か月"] - t["2019年"]).sort_values()
ui.readout([
    f"いちばん稼働率が高いのは **{t['直近12か月'].idxmax()}**（{t['直近12か月'].max():.0f}%）、低いのは **{t['直近12か月'].idxmin()}**（{t['直近12か月'].min():.0f}%）。",
    f"2019年より上がったのは {'・'.join(dd[dd > 0.5].index) or 'なし'}、下がったのは {'・'.join(dd[dd < -0.5].index) or 'なし'} です。",
], source="観光庁「宿泊旅行統計調査」")

# ---- 3. 種類×月 ----
ui.block("🗓️ 宿の種類ごとの、月ごとの稼働率",
         f"{fy}年の客室稼働率を、宿の種類（縦）と月（横）で並べたもの。色が濃いほど埋まっている",
         "宿の種類ごとに、空きが出やすい月（てこ入れの余地がある月）を探したいとき")
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
ui.block("⚖️ 宿の種類ごとの、全国との差",
         "直近12か月の客室稼働率について、長野県から全国を引いた差。右（青）なら全国より高く、左（オレンジ）なら低い",
         "長野県の宿のうち、全国と比べて伸びしろの大きい種類を知りたいとき")
dn = (recent - recent_nat).reindex(TYPES).dropna().sort_values()
fig = go.Figure(go.Bar(
    y=dn.index, x=dn.values, orientation="h", marker_color=[charts.MAIN if v >= 0 else charts.SECOND for v in dn.values],
    text=[f"{v:+.1f}pt" for v in dn.values], textposition="outside", cliponaxis=False,
    customdata=[[recent[k], recent_nat[k]] for k in dn.index],
    hovertemplate="%{y}<br>長野県 %{customdata[0]:.1f}% ／ 全国 %{customdata[1]:.1f}%<extra></extra>",
))
lim = max(abs(dn).max() * 1.3, 5)
charts.layout(fig, height=300)
fig.update_xaxes(range=[-lim, lim], ticksuffix="pt", zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
fig.update_yaxes(showgrid=False)
st.plotly_chart(fig, use_container_width=True)
ui.readout([
    f"全国との差がいちばん大きいのは **{dn.index[0]}**（{dn.iloc[0]:+.1f}ポイント）です。",
    f"全国より高いのは {'・'.join(dn[dn > 0].index)} です。" if (dn > 0).any() else "どの種類も全国より低くなっています。",
], source="観光庁「宿泊旅行統計調査」")

ui.sources(["shukuhaku"])

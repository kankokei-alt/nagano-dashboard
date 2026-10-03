import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib import charts, data, ui
from lib.charts import man, updown

ui.setup("海外からのお客さま", "どの国・地域から、いつ、県内のどこに。全国の動きから先行きも。")

s = data.shukuhaku()
last = s.index.max()
ly = last - pd.DateOffset(years=1)
f12 = s.foreign.rolling(12).sum()
nat = data.shukuhaku_nationality()
ny = int(nat.ym.dt.year.max())
by = nat[nat.ym.dt.year == ny].groupby("country").value.sum()
base = nat[nat.ym.dt.year == 2019].groupby("country").value.sum()
named = by.drop("その他", errors="ignore").sort_values(ascending=False)

# 全国の訪日客（JNTO）
jn = data.jnto()
J = jn[jn.kind.isin(["total", "country", "sub"])].pivot_table(index="ym", columns="country", values="value")
j_status = jn[jn.kind == "total"].set_index("ym").status
jl = J.index.max()
j_yoy = J / J.shift(12, freq="MS").reindex(J.index)
w = by.drop("その他", errors="ignore").rename({"オーストラリア": "豪州"})
w = w[w.index.isin(J.columns)] / w[w.index.isin(J.columns)].sum()
wg = (j_yoy[w.index] * w).sum(axis=1) / (j_yoy[w.index].notna() * w).sum(axis=1)
wg = wg[j_yoy["総数"].notna()]

ui.insight(
    f"{last.year}年{last.month}月までの1年間に泊まった外国人は延べ <b>{man(f12[last], '人泊')}</b>（前年同期より{updown(f12[last] / f12[ly] - 1)}）。"
    f"{ny}年にいちばん多かったのは <b>{named.index[0]}</b>（{named.iloc[0] / by.sum():.0%}）で、{named.index[1]}・{named.index[2]}が続きます。"
    f"<br>一足早く分かる全国の訪日客（{jl.year}年{jl.month}月）は、長野のお客さまの国・地域の構成に合わせると前年より{updown(wg[jl] - 1)}です。"
)

# ---- 1. 月ごとの外国人宿泊 ----
ui.block("📊 外国人の宿泊者数（月ごと）", "外国人延べ宿泊者数（今年・前年・2019年）", "インバウンドの勢いを確かめたいとき")
fig = go.Figure()
for y, label, color, dash in [(2019, "2019年（コロナ前）", charts.CONTEXT, "dot"), (last.year - 1, f"{last.year - 1}年", charts.CONTEXT, "solid"),
                              (last.year, f"{last.year}年", charts.MAIN, "solid")]:
    v = s[s.index.year == y].foreign
    fig.add_trace(go.Scatter(x=v.index.month, y=v / 1e4, name=label, mode="lines+markers",
                             line={"color": color, "width": 3 if y == last.year else 2, "dash": dash},
                             hovertemplate=f"{label} %{{x}}月 %{{y:,.1f}}万人泊<extra></extra>"))
charts.layout(fig, height=320, hovermode="x unified")
fig.update_xaxes(tickvals=list(range(1, 13)), ticktext=[f"{m}月" for m in range(1, 13)])
fig.update_yaxes(title="外国人延べ宿泊者数（万人泊）", rangemode="tozero")
st.plotly_chart(fig, use_container_width=True)
full = s[s.index.year == last.year - 1].foreign
winter = full[full.index.month.isin([12, 1, 2])].sum() / full.sum()
cy = s[s.index.year == last.year].foreign
c19 = s[(s.index.year == 2019) & (s.index.month <= last.month)].foreign.sum()
ui.readout([
    f"{last.year - 1}年は **{full.idxmax().month}月** がいちばん多く、冬（12〜2月）の3か月に1年の **{winter:.0%}** が集まっています。",
    f"{last.year}年1〜{last.month}月の合計は {man(cy.sum(), '人泊')} で、2019年の同じ期間の **{cy.sum() / c19:.1f} 倍** です。",
    f"泊まった人全体に占める外国人の割合は、{last.year}年{last.month}月で {s.loc[last].foreign / s.loc[last].guests:.0%}、"
    f"{full.idxmax().month}月には {s.loc[full.idxmax()].foreign / s.loc[full.idxmax()].guests:.0%} まで高まります。",
], source="観光庁「宿泊旅行統計調査」" + (f"（{last.year}年は速報値）" if s.loc[last].status == "速報" else ""))

# ---- 2. 国・地域別 ----
ui.block("🌏 どの国・地域から来ているか", "国・地域別の割合と2019年比", "どの市場に向けて動くか決めるとき")
top = named.head(10)
bars = pd.concat([top, pd.Series({"そのほか": by.sum() - top.sum()})]).iloc[::-1]
chg = bars / base.reindex(bars.index) - 1
fig = go.Figure(go.Bar(
    y=bars.index, x=bars.values / by.sum(), orientation="h",
    marker_color=[charts.CONTEXT if k == "そのほか" else charts.MAIN for k in bars.index],
    text=[f"{v / by.sum():.0%}" + ("" if pd.isna(c) else f"（2019年比 {c:+.0%}）") for v, c in zip(bars.values, chg)],
    textposition="outside", cliponaxis=False,
    hovertemplate="<b>%{y}</b> %{x:.1%}<extra></extra>",
))
charts.layout(fig, height=380)
fig.update_xaxes(tickformat=".0%", range=[0, bars.max() / by.sum() * 1.6], title=f"{ny}年の外国人延べ宿泊者数に占める割合")
fig.update_yaxes(showgrid=False)
st.plotly_chart(fig, use_container_width=True)
grow = (top / base.reindex(top.index) - 1).dropna().sort_values(ascending=False)
ui.readout([
    f"上位3つ（{'・'.join(top.index[:3])}）で全体の **{top.iloc[:3].sum() / by.sum():.0%}** を占めます。",
    f"2019年から大きく伸びたのは **{grow.index[0]}**（{grow.iloc[0]:+.0%}）と **{grow.index[1]}**（{grow.iloc[1]:+.0%}）、"
    f"伸びが小さい（または減った）のは {grow.index[-1]}（{grow.iloc[-1]:+.0%}）です。",
], source=f"観光庁「宿泊旅行統計調査」（{ny}年確定値, 参考第1表）。国籍別は従業者10人以上の施設の集計")

# ---- 3. 国・地域×月 ----
ui.block("🗓️ 国・地域ごとの「来る季節」", "国・地域ごとの月別の割合", "市場ごとの準備時期を決めるとき")
hm = nat[(nat.ym.dt.year == ny) & nat.country.isin(top.index)].pivot_table(index="country", columns=nat.ym.dt.month, values="value")
hm = hm.reindex(top.index)
hm = hm.div(hm.sum(axis=1), axis=0)
fig = go.Figure(go.Heatmap(
    z=hm.values, x=[f"{m}月" for m in hm.columns], y=hm.index, colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]],
    zmin=0, text=[[f"{v:.0%}" for v in row] for row in hm.values], texttemplate="%{text}", textfont={"size": 11},
    hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "1年に<br>占める割合", "tickformat": ".0%"},
    xgap=2, ygap=2,
))
charts.layout(fig, height=420)
fig.update_yaxes(autorange="reversed", showgrid=False)
fig.update_xaxes(side="top")
st.plotly_chart(fig, use_container_width=True)
peak = hm.idxmax(axis=1)
winter_c = [c for c in hm.index if hm.loc[c, [12, 1, 2]].sum() >= 0.5]
summer_c = [c for c in hm.index if hm.loc[c, [7, 8, 9]].sum() >= 0.3]
ui.readout([
    f"1年の半分以上が冬（12〜2月）に集中しているのは **{'・'.join(winter_c)}** です。" if winter_c else "",
    f"夏から秋（7〜9月）にも多いのは **{'・'.join(summer_c)}** です。" if summer_c else "",
    "それぞれのピークの月: " + "、".join(f"{c} {m}月" for c, m in peak.items()) + "。",
], source=f"観光庁「宿泊旅行統計調査」（{ny}年確定値）")

# ---- 4. 主な国・地域の推移 ----
ui.block("📈 主な国・地域の移り変わり（年ごと）", "上位6か国・地域の年ごとの推移", "伸びている市場を見極めたいとき")
top6 = named.head(6).index
yr = nat[nat.country.isin(top6)].groupby([nat.ym.dt.year, "country"]).value.sum().unstack()
fig = make_subplots(rows=2, cols=3, subplot_titles=list(top6), shared_xaxes=True, vertical_spacing=0.14)
for i, c in enumerate(top6):
    v = yr[c].dropna()
    fig.add_trace(go.Scatter(x=v.index, y=v / 1e4, mode="lines+markers", line={"color": charts.MAIN, "width": 2},
                             marker={"size": 5}, showlegend=False, hovertemplate=f"{c} %{{x}}年 %{{y:,.1f}}万人泊<extra></extra>"),
                  row=i // 3 + 1, col=i % 3 + 1)
charts.layout(fig, height=440)
fig.update_yaxes(rangemode="tozero", title_text="")
st.plotly_chart(fig, use_container_width=True)
st.caption("縦軸の単位は万人泊。国・地域ごとに目盛りが違います。")
r19 = (yr.loc[ny] / yr.loc[2019]).sort_values(ascending=False)
ui.readout([
    "コロナ前の2019年と比べた倍率: " + "、".join(f"{c} {v:.1f}倍" for c, v in r19.items()) + "。",
    f"いちばん伸びたのは **{r19.index[0]}** です。" + (f"**{r19.index[-1]}** は2019年を下回っています。" if r19.iloc[-1] < 1 else ""),
], source="観光庁「宿泊旅行統計調査」（年の確定値）")

# ---- 5. 県内のどこに泊まっているか ----
ui.block("📍 県内のどのエリアに泊まっているか", "5エリア別の外国人宿泊と、その割合", "受け入れが進む地域を知りたいとき")
ar = data.shukuhaku_area()
ay = int(ar.ym.dt.year.max())
a = ar[ar.ym.dt.year == ay].groupby("area")[["guests", "foreign"]].sum()
a.index = a.index.str.replace("長野県", "")
a["share"] = a.foreign / a.guests
a = a.sort_values("foreign")
c1, c2 = st.columns(2)
with c1:
    fig = go.Figure(go.Bar(y=a.index, x=a.foreign / 1e4, orientation="h", marker_color=charts.MAIN,
                           text=[f"{v / 1e4:,.0f}万" for v in a.foreign], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y} %{x:,.1f}万人泊<extra></extra>"))
    charts.layout(fig, height=280, title={"text": "外国人延べ宿泊者数（万人泊）", "font": {"size": 14}})
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)
with c2:
    fig = go.Figure(go.Bar(y=a.index, x=a.share, orientation="h", marker_color=charts.SECOND,
                           text=[f"{v:.0%}" for v in a.share], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y} 外国人の割合 %{x:.1%}<extra></extra>"))
    charts.layout(fig, height=280, title={"text": "宿泊者に占める外国人の割合", "font": {"size": 14}})
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)
amap = data.shukuhaku_area_map()
ui.readout([
    f"外国人がいちばん多く泊まっているのは **{a.foreign.idxmax()}** エリアで、県全体の外国人宿泊の {a.foreign.max() / a.foreign.sum():.0%} を占めます。",
    ("宿泊者に占める外国人の割合がいちばん高いのも同じ" if a.share.idxmax() == a.foreign.idxmax() else "宿泊者に占める外国人の割合がいちばん高いのは")
    + f" **{a.share.idxmax()}**（{a.share.max():.0%}）、"
    f"いちばん低いのは **{a.share.idxmin()}**（{a.share.min():.0%}）です。",
], source=f"観光庁「宿泊旅行統計調査」広域市町村（130区分）別参考表（{ay}年）")
with st.expander("5エリアに入る市町村"):
    st.dataframe(amap, hide_index=True, use_container_width=True)

# ---- 6. 全国の訪日客（先行指標） ----
ui.block("🛫 全国の訪日客の動き（先行指標）", "全国の訪日客と県の外国人宿泊の前年比", "先行きを早めにつかみたいとき")
ng = s.foreign / s.foreign.shift(12, freq="MS").reindex(s.index)
ev = data.events()
covid = ev[ev.kind == "covid"]
cv0, cv1 = covid.start.min().to_period("M").to_timestamp(), covid.end.max().to_period("M").to_timestamp()
both = pd.DataFrame({"wg": wg, "ng": ng}).dropna()
normal = both[[not (cv0 <= t <= cv1 or cv0 <= t - pd.DateOffset(years=1) <= cv1) for t in both.index]]
agree = ((normal.wg > 1) == (normal.ng > 1)).mean()
lead = (jl.year - last.year) * 12 + jl.month - last.month
since = jl - pd.DateOffset(months=23)
fig = go.Figure()
for label, v, color, dash in [("全国の訪日客（総数）", j_yoy["総数"], charts.CONTEXT, "dot"),
                              ("全国の訪日客（長野の客層に合わせた伸び）", wg, charts.SECOND, "solid"),
                              ("長野県の外国人延べ宿泊者", ng, charts.MAIN, "solid")]:
    v = (v[v.index >= since].dropna() - 1) * 100
    est = [j_status.get(t) == "推計" and "宿泊" not in label for t in v.index]
    fig.add_trace(go.Scatter(x=v.index, y=v.values, name=label, mode="lines+markers",
                             line={"color": color, "width": 3 if "長野県" in label else 2, "dash": dash},
                             marker={"size": 8, "symbol": ["circle-open" if e else "circle" for e in est]},
                             hovertemplate=f"{label}<br>%{{x|%Y年%-m月}} 前年同月比 %{{y:+.0f}}%<extra></extra>"))
fig.add_hline(y=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
charts.layout(fig, height=360, hovermode="x unified")
fig.update_yaxes(title="前年同月比（%）", ticksuffix="%")
fig.update_xaxes(tickformat="%Y年<br>%-m月", dtick="M3")
st.plotly_chart(fig, use_container_width=True)
st.caption("白抜きの点は推計値。")
top_m = w.sort_values(ascending=False).head(6)
g3 = J.loc[jl - pd.DateOffset(months=2):jl, top_m.index].sum() / J.loc[
    jl - pd.DateOffset(months=14):jl - pd.DateOffset(months=12), top_m.index].sum() - 1
ui.readout([
    f"全国の訪日客の数字は、宿泊旅行統計より **{lead}か月早く** 公表されます。",
    f"長野の客層に合わせた全国の伸びは、コロナ期間を除く過去の月の **{agree:.0%}** で、長野県の外国人宿泊と増減の向きがそろっていました。",
    f"最新の{jl.year}年{jl.month}月は、全国の総数が前年より{updown(j_yoy.loc[jl, '総数'] - 1)}、長野の客層に合わせると{updown(wg[jl] - 1)}"
    + ("で、県内の外国人宿泊も前年を下回る可能性があります。" if wg[jl] < 0.995 else
       "で、県内の外国人宿泊も前年を上回る可能性があります。" if wg[jl] > 1.005 else "で、前年並みになりそうです。"),
    "長野の主なお客さまの国・地域の、全国での直近3か月の伸び: " + "、".join(f"{c} {v:+.0%}" for c, v in g3.items()) + "。",
], source="日本政府観光局（JNTO）「訪日外客統計」、観光庁「宿泊旅行統計調査」")

ui.sources(["shukuhaku", "jnto", "irikomi"])

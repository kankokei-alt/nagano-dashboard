import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, kouiki, muni, ui
from lib.charts import man

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}の季節のかぶり・すき間", "市町村ごとのピークの月が重なっているか、ずれているか。", kicker="広域連携")
k, mem = kouiki.picker("season")
LABEL = kouiki.label(k)

muni.require_digital()
v = muni.visitors()
mem = [c for c in mem if c in v]
if not mem:
    st.info("市町村を選んでください。")
    st.stop()
y = muni.yearly()
ry = int(y.index.max())
MON = [f"{m}月" for m in range(1, 13)]
names = muni.master().name
cur = v[v.index.year == ry][mem]
cur.index = cur.index.month
km = cur.sum(axis=1)
pref = v[v.index.year == ry].sum(axis=1)
pref.index = pref.index.month
ksh, psh = km / km.sum(), pref / pref.sum()
hm = cur.div(cur.sum(), axis=1).T
hm = hm.loc[cur.sum().sort_values(ascending=False).index]
peaks = hm.idxmax(axis=1)
pmode = peaks.mode().iloc[0]

ui.insight(
    f"{ry}年の{LABEL}は <b>{km.idxmax()}月</b> がいちばん多く（1年の {ksh.max():.0%}）、<b>{km.idxmin()}月</b> がいちばん少ない（{ksh.min():.0%}）。"
    + (f"{len(hm)}市町村のうち {(peaks == pmode).sum()} が {pmode}月にピークを迎えます。" if len(hm) > 1 else "")
)

with ui.card():
    ui.block("市町村ごとの季節", f"{ry}年。各市町村の1年を100%とした月別の割合。色が濃いほど多い")
    fig = go.Figure(go.Heatmap(
        z=hm.values, x=MON, y=[names[c] for c in hm.index], colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]], zmin=0,
        text=[[f"{x:.0%}" for x in r] for r in hm.values], texttemplate="%{text}", textfont={"size": 10}, xgap=2, ygap=2,
        hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "割合", "tickformat": ".0%"},
    ))
    charts.layout(fig, height=80 + 32 * len(hm))
    fig.update_xaxes(side="top")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    ui.chart(fig)
    diff_peak = peaks[peaks != pmode]
    ui.readout([
        "それぞれのピーク: " + "、".join(f"{names[c]} {m}月" for c, m in peaks.items()) + "。",
        (f"ピークが違う市町村（{'・'.join(names[c] for c in diff_peak.index)}）があり、時期をずらした周遊の組み合わせが考えられます。"
         if len(diff_peak) else "どの市町村も同じ月にピークを迎えます。少ない月をどう埋めるかが共通の課題です。") if len(hm) > 1 else "",
    ], source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成（{ry}年）")

with ui.card():
    ui.block("圏域と県全体の季節", f"{ry}年。それぞれの1年を100%とした月別の割合")
    fig = go.Figure()
    for vv, label, color in [(ksh, LABEL, charts.MAIN), (psh, "県全体", charts.CONTEXT)]:
        fig.add_trace(go.Bar(x=MON, y=vv.values, name=label, marker_color=color, marker_line={"color": "white", "width": 1},
                             hovertemplate=f"{label} %{{x}}: 1年の %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=320, barmode="group", bargap=0.2)
    fig.update_yaxes(tickformat=".0%")
    ui.chart(fig)
    d = ksh - psh
    low = d[d < -0.005].index
    ui.readout([
        f"県全体と比べて多いのは **{d.idxmax()}月**（{d.max() * 100:+.1f}ポイント）、少ないのは **{d.idxmin()}月**（{d.min() * 100:+.1f}ポイント）です。",
        f"県全体より割合が低い月（すき間）: {'・'.join(f'{m}月' for m in low)}。" if len(low) else "",
    ], source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成（{ry}年。{kouiki.SUM_NOTE}）")

with ui.card():
    ui.block("月別の観光来訪者数", "圏域の市町村の合計。年ごと")
    kk = v[mem].sum(axis=1)
    Y = kk.index.max().year
    fig = go.Figure()
    for yy in sorted(set(kk.index.year)):
        r = kk[kk.index.year == yy]
        color = charts.MAIN if yy == Y else charts.SECOND if yy == Y - 1 else charts.CONTEXT
        fig.add_trace(go.Scatter(x=[f"{m}月" for m in r.index.month], y=r.values / 1e4, name=f"{yy}年", mode="lines+markers",
                                 line={"color": color, "width": 3.5 if yy == Y else 2 if yy == Y - 1 else 1.3},
                                 opacity=1 if yy >= Y - 1 else .7, hovertemplate=f"{yy}年 %{{x}} %{{y:,.1f}}万人<extra></extra>"))
    charts.layout(fig, height=340, hovermode="x unified")
    fig.update_yaxes(title="万人", rangemode="tozero")
    ui.chart(fig)
    r = kk[kk.index.year == Y]
    prev = kk.reindex(r.index - pd.DateOffset(years=1)).values
    dd = pd.Series(r.values / prev - 1, index=r.index.month)
    ui.readout([
        f"{Y}年に前年を上回った月: {'・'.join(f'{m}月' for m in dd[dd > 0].index) or 'なし'}。",
        f"{ry}年の最多は {km.idxmax()}月（{man(km.max())}）です。",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

ui.sources(["digital"])

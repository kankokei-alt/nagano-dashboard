import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, muni, ui
from lib.charts import man

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}はいつ来ている？", "月ごとの波と、その形が年によってどう変わってきたか。", kicker="市町村")
code = muni.picker("season")

a = muni.annual()
mine = a[a.municipality_code == code].set_index("year")
mon = mine[charts.MONTHS].dropna(how="all")
mon = mon[mon.sum(axis=1) > 0]
if mon.empty:
    st.info(f"{NAME}には、月別の内訳がある観光地がありません。")
    st.stop()
ry = int(mon.index.max())
MON = [f"{m}月" for m in range(1, 13)]
cov = mine.coverage.loc[ry]
cur = mon.loc[ry]
pref = a[a.year == ry][charts.MONTHS].sum()
pref_sh = pref / pref.sum()
cur_sh = cur / cur.sum()

peak, low = int(cur.idxmax()[1:]), int(cur.idxmin()[1:])
ui.insight(
    f"{ry}年の{NAME}は <b>{peak}月</b> がいちばん多く（1年の {cur.max() / cur.sum():.0%}）、"
    f"<b>{low}月</b> がいちばん少ない（{cur.min() / cur.sum():.0%}）。多い月は少ない月の約 {cur.max() / max(cur.min(), 1):.1f} 倍です。"
    + (f"<br><small>月別の内訳がある観光地の合計（{ry}年の延べ利用者数の {cov:.0%}）で計算しています。</small>" if cov < 0.995 else "")
)

# ---- 1. 月別 ----
with ui.card():
    ui.block("月別の延べ利用者数", f"{ry}年・前年・2019年")
    fig = go.Figure()
    for y, color, width, dash in [(2019, charts.CONTEXT, 2, "dot"), (ry - 1, charts.CONTEXT, 2, "solid"), (ry, charts.MAIN, 3, "solid")]:
        if y not in mon.index:
            continue
        label = f"{y}年" + ("（コロナ前）" if y == 2019 else "")
        fig.add_trace(go.Scatter(x=MON, y=mon.loc[y].values / 1e4, name=label, mode="lines+markers",
                                 line={"color": color, "width": width, "dash": dash}, marker={"size": 7},
                                 hovertemplate=f"{label} %{{x}} %{{y:,.1f}}万人<extra></extra>"))
    charts.layout(fig, height=340, hovermode="x unified")
    fig.update_yaxes(title="万人", rangemode="tozero")
    ui.chart(fig)
    pts = []
    if ry - 1 in mon.index:
        d = (mon.loc[ry] / mon.loc[ry - 1] - 1)
        pts.append(f"前年より大きく増えた月は **{int(d.idxmax()[1:])}月**（{d.max():+.0%}）、減った月は **{int(d.idxmin()[1:])}月**（{d.min():+.0%}）です。")
    if 2019 in mon.index:
        d19 = mon.loc[ry] / mon.loc[2019] - 1
        pts.append(f"2019年を上回った月: {'・'.join(f'{int(k[1:])}月' for k in d19[d19 > 0].index) or 'なし'}。")
    ui.readout(pts, source="長野県「観光地利用者統計調査」（月別の内訳がある観光地の合計）")

# ---- 2. 県全体との季節の違い ----
with ui.card():
    ui.block("県全体との季節の違い", f"{ry}年。それぞれの1年を100%とした月別の割合")
    fig = go.Figure()
    for v, label, color in [(cur_sh, NAME, charts.MAIN), (pref_sh, "県全体", charts.CONTEXT)]:
        fig.add_trace(go.Bar(x=MON, y=v.values, name=label, marker_color=color, marker_line={"color": "white", "width": 1},
                             hovertemplate=f"{label} %{{x}}: 1年の %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=320, barmode="group", bargap=0.2)
    fig.update_yaxes(tickformat=".0%")
    ui.chart(fig)
    diff = (cur_sh - pref_sh)
    ui.readout([
        f"県全体と比べて特に多いのは **{int(diff.idxmax()[1:])}月**（{diff.max() * 100:+.1f}ポイント）、少ないのは **{int(diff.idxmin()[1:])}月**（{diff.min() * 100:+.1f}ポイント）です。",
        f"冬（12〜2月）の割合は {NAME} {cur_sh[['m12', 'm01', 'm02']].sum():.0%}、県全体 {pref_sh[['m12', 'm01', 'm02']].sum():.0%}。"
        f"夏（7〜8月）は {NAME} {cur_sh[['m07', 'm08']].sum():.0%}、県全体 {pref_sh[['m07', 'm08']].sum():.0%} です。",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

# ---- 3. 年×月 ----
with ui.card():
    ui.block("季節の形の移り変わり", "年（縦）×月（横）。各年の1年を100%とした割合。色が濃いほど多い")
    sh = mon.div(mon.sum(axis=1), axis=0)
    fig = go.Figure(go.Heatmap(
        z=sh.values, x=MON, y=[f"{y}年" for y in sh.index], colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]],
        zmin=0, text=[[f"{v:.0%}" for v in r] for r in sh.values], texttemplate="%{text}", textfont={"size": 10}, xgap=2, ygap=2,
        hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "割合", "tickformat": ".0%"},
    ))
    charts.layout(fig, height=60 + 28 * len(sh))
    fig.update_xaxes(side="top")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    ui.chart(fig)
    peaks = sh.idxmax(axis=1).map(lambda k: int(k[1:]))
    ui.readout([
        f"いちばん多い月は、{'・'.join(f'{m}月（{(peaks == m).sum()}回）' for m in peaks.value_counts().index)} でした（{sh.index.min()}〜{ry}年）。",
        "2020・2021年はコロナの影響で形が大きく崩れています。" if {2020, 2021} <= set(sh.index) else "",
    ], source="長野県「観光地利用者統計調査」。2016年以降は月別の内訳がない観光地を除いて計算")

# ---- 4. 観光地×月 ----
sp = data.riyousha_spots()
s = sp[(sp.municipality_code == code) & (sp.year == ry)].dropna(subset=charts.MONTHS).sort_values("total", ascending=False)
s = s[s[charts.MONTHS].sum(axis=1) > 0]
if len(s) >= 2:
    with ui.card():
        ui.block("観光地ごとの季節", f"{ry}年。各観光地の1年を100%とした月別の割合")
        hm = s.set_index("spot")[charts.MONTHS]
        hm = hm.div(hm.sum(axis=1), axis=0)
        fig = go.Figure(go.Heatmap(
            z=hm.values, x=MON, y=hm.index, colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]], zmin=0,
            text=[[f"{v:.0%}" for v in r] for r in hm.values], texttemplate="%{text}", textfont={"size": 10}, xgap=2, ygap=2,
            hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "割合", "tickformat": ".0%"},
        ))
        charts.layout(fig, height=70 + 30 * len(hm))
        fig.update_xaxes(side="top")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        ui.chart(fig)
        pk = hm.idxmax(axis=1).map(lambda k: int(k[1:]))
        ui.readout([
            "それぞれいちばん多い月: " + "、".join(f"{k} {v}月" for k, v in pk.items()) + "。",
            f"季節の差がいちばん大きいのは **{(hm.max(axis=1) - hm.min(axis=1)).idxmax()}**、1年を通して来るのは **{(hm.max(axis=1) - hm.min(axis=1)).idxmin()}** です。",
        ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

ui.sources(["riyousha"])

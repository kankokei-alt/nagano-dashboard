import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, data, muni, ui
from lib.charts import man

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}はいつ来ている？", "月ごとの波と、その形が年によってどう変わってきたか。", kicker="市町村")
code = muni.picker("season")
cmp = muni.compare_picker(code, "season")

v = muni.visitors()
if code not in v:
    st.info(f"{NAME}は、デジタル観光統計オープンデータに観光来訪者数がありません。")
    st.stop()
mv = v[code]
MON = [f"{m}月" for m in range(1, 13)]
y = muni.yearly()
ry = int(y.index.max())
Y, M = muni.latest()
mon = pd.DataFrame({yy: mv[mv.index.year == yy].set_axis(mv[mv.index.year == yy].index.month) for yy in sorted(set(mv.index.year))}).T
mon = mon.reindex(columns=range(1, 13))
cur = mon.loc[ry]
pref = v[v.index.year == ry].sum(axis=1)
pref.index = pref.index.month
pref_sh, cur_sh = pref / pref.sum(), cur / cur.sum()

peak, low = int(cur.idxmax()), int(cur.idxmin())
ui.insight(
    f"{ry}年の{NAME}は <b>{peak}月</b> がいちばん多く（1年の {cur.max() / cur.sum():.0%}）、"
    f"<b>{low}月</b> がいちばん少ない（{cur.min() / cur.sum():.0%}）。多い月は少ない月の約 {cur.max() / max(cur.min(), 1):.1f} 倍です。"
)

# ---- 1. 月別 ----
with ui.card():
    ui.block("月別の観光来訪者数", f"{Y}年（{M}月まで）と過去の年")
    fig = go.Figure()
    years = list(mon.index)
    for yy in years:
        is_now = yy == Y
        color = charts.MAIN if is_now else charts.SECOND if yy == Y - 1 else charts.CONTEXT
        width = 3.5 if is_now else 2.2 if yy == Y - 1 else 1.4
        r = mon.loc[yy].dropna()
        fig.add_trace(go.Scatter(x=[f"{m}月" for m in r.index], y=r.values / 1e4, name=f"{yy}年", mode="lines+markers",
                                 line={"color": color, "width": width}, marker={"size": 6 if yy >= Y - 1 else 4},
                                 opacity=1 if yy >= Y - 1 else .7, hovertemplate=f"{yy}年 %{{x}} %{{y:,.1f}}万人<extra></extra>"))
    charts.layout(fig, height=340, hovermode="x unified")
    fig.update_yaxes(title="万人", rangemode="tozero")
    ui.chart(fig)
    d = (mon.loc[Y] / mon.loc[Y - 1] - 1).dropna() if Y - 1 in mon.index else pd.Series(dtype=float)
    ui.readout([
        (f"{Y}年に前年より大きく増えた月は **{int(d.idxmax())}月**（{d.max():+.0%}）" if d.max() > 0 else f"{Y}年は前年を上回った月がありません")
        + (f"、大きく減った月は **{int(d.idxmin())}月**（{d.min():+.0%}）です。" if d.min() < 0 else "。どの月も前年を上回っています。") if len(d) else "",
        f"{ry}年にいちばん多かったのは {peak}月（{man(cur.max())}）、少なかったのは {low}月（{man(cur.min())}）です。",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

# ---- 2. 県全体との季節の違い ----
with ui.card():
    ui.block("県全体との季節の違い", f"{ry}年。それぞれの1年を100%とした月別の割合")
    fig = go.Figure()
    for vv, label, color in [(cur_sh, NAME, charts.MAIN), (pref_sh, "県全体", charts.CONTEXT)]:
        fig.add_trace(go.Bar(x=MON, y=vv.values, name=label, marker_color=color, marker_line={"color": "white", "width": 1},
                             hovertemplate=f"{label} %{{x}}: 1年の %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=320, barmode="group", bargap=0.2)
    fig.update_yaxes(tickformat=".0%")
    ui.chart(fig)
    diff = cur_sh - pref_sh
    w, s_ = [12, 1, 2], [7, 8]
    ui.readout([
        f"県全体と比べて特に多いのは **{int(diff.idxmax())}月**（{diff.max() * 100:+.1f}ポイント）、少ないのは **{int(diff.idxmin())}月**（{diff.min() * 100:+.1f}ポイント）です。",
        f"冬（12〜2月）の割合は {NAME} {cur_sh[w].sum():.0%}、県全体 {pref_sh[w].sum():.0%}。"
        f"夏（7〜8月）は {NAME} {cur_sh[s_].sum():.0%}、県全体 {pref_sh[s_].sum():.0%} です。",
    ], source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成（{ry}年。県全体は77市町村の合計）")

# ---- 比べる ----
with ui.card():
    ui.block("比べる：季節の形", f"{ry}年。それぞれの1年を100%とした月別の割合")
    yr = v[v.index.year == ry]
    sh = yr / yr.sum()
    sh.index = MON
    fig = compare.lines(cmp, sh[[c for c in cmp.all if c in sh]], pref=pref_sh.set_axis(MON), hover="%{y:.1%}", pref_label="県全体")
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    ui.chart(fig)
    compare.hint(cmp)
    pk = sh.idxmax()
    pts = [f"いちばん多い月: " + "、".join(f"{cmp.label(c)} {pk[c]}" for c in cmp.all if c in pk) + f"（県全体 {MON[int(pref_sh.idxmax()) - 1]}）。"]
    wsh = sh.loc[["12月", "1月", "2月"]].sum()
    pts += compare.readout(cmp, wsh, pref_sh[w].sum(), "冬（12〜2月）の割合", fmt=lambda x: f"{x:.0%}", pref_label="県全体")
    ui.readout(pts, source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成（{ry}年）")

# ---- 3. 年×月 ----
with ui.card():
    ui.block("季節の形の移り変わり", "年（縦）×月（横）。各年の1年を100%とした割合。色が濃いほど多い")
    full = mon.loc[[yy for yy in mon.index if yy in y.index]]
    sh2 = full.div(full.sum(axis=1), axis=0)
    fig = go.Figure(go.Heatmap(
        z=sh2.values, x=MON, y=[f"{yy}年" for yy in sh2.index], colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]],
        zmin=0, text=[[f"{x:.0%}" for x in r] for r in sh2.values], texttemplate="%{text}", textfont={"size": 10}, xgap=2, ygap=2,
        hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "割合", "tickformat": ".0%"},
    ))
    charts.layout(fig, height=80 + 34 * len(sh2))
    fig.update_xaxes(side="top")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    ui.chart(fig)
    peaks = sh2.idxmax(axis=1)
    ui.readout([
        f"いちばん多い月は、{'・'.join(f'{m}月（{(peaks == m).sum()}回）' for m in peaks.value_counts().index)} でした（{sh2.index.min()}〜{ry}年）。",
        "2021年はコロナの影響で形が崩れています。" if 2021 in sh2.index else "",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

# ---- 4. 観光地×月 ----
sp = data.riyousha_spots()
ry = int(sp.year.max())
s = sp[(sp.municipality_code == code) & (sp.year == ry)].dropna(subset=charts.MONTHS).sort_values("total", ascending=False)
s = s[s[charts.MONTHS].sum(axis=1) > 0]
if len(s) >= 2:
    with ui.card():
        ui.block("観光地ごとの季節", f"{ry}年。県の調査対象の観光地ごとに、1年を100%とした月別の割合")
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

ui.sources(["digital", "riyousha"])

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, data, muni, ui
from lib.charts import updown, yen

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}でいくら使っている？", "県の調査対象の観光地での消費額と、1人あたりの金額。", kicker="市町村")
code = muni.picker("spend")
cmp = muni.compare_picker(code, "spend")

a = muni.annual()
mine = a[a.municipality_code == code].set_index("year")
mine = mine[mine.spend > 0]
if mine.empty:
    st.info(f"{NAME}には、観光地での消費額のデータがありません。")
    st.stop()
ry = int(mine.index.max())
cur = mine.loc[ry]
per = mine.spend / mine.total
pref = a.groupby("year")[["spend", "total"]].sum()
pref_per = pref.spend / pref.total
t = muni.table(ry)

ui.insight(
    f"{ry}年の{NAME}の調査対象の観光地での消費額は <b>{yen(cur.spend)}</b>"
    + (f"（前年より{updown(cur.spend / mine.loc[ry - 1, 'spend'] - 1)}）" if ry - 1 in mine.index else "")
    + f"。1人あたりでは <b>{per[ry]:,.0f}円</b> で、県全体（{pref_per[ry]:,.0f}円）"
    + ("より高く" if per[ry] > pref_per[ry] * 1.03 else "より低く" if per[ry] < pref_per[ry] * 0.97 else "と同じくらいで")
    + f"、県内 {muni.rank(t, 'per_visit', code)} です。"
)

# ---- 1. 推移 ----
with ui.card():
    ui.block("観光地での消費額と1人あたりの推移", "年ごと。調査対象の観光地の合計。1人あたりは県全体と比較")
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(x=mine.index, y=mine.spend / 1e8, marker_color=charts.MAIN,
                               hovertemplate="%{x}年 %{y:,.1f}億円<extra></extra>"))
        charts.layout(fig, height=300, bargap=0.25, title={"text": "観光地での消費額（億円）", "font": {"size": 14}})
        fig.update_xaxes(dtick=2)
        ui.chart(fig)
    with c2:
        fig = go.Figure()
        for v, label, color, dash in [(per, NAME, charts.MAIN, "solid"), (pref_per.reindex(per.index), "県全体", charts.CONTEXT, "dot")]:
            fig.add_trace(go.Scatter(x=v.index, y=v, name=label, mode="lines+markers", line={"color": color, "width": 2.5, "dash": dash},
                                     hovertemplate=f"%{{x}}年 {label} 1人あたり %{{y:,.0f}}円<extra></extra>"))
        charts.layout(fig, height=300, hovermode="x unified", title={"text": "1人あたりの消費額（円）", "font": {"size": 14}})
        fig.update_xaxes(dtick=2)
        fig.update_yaxes(rangemode="tozero")
        ui.chart(fig)
    first = int(mine.index.min())
    ui.readout([
        f"{first}年から{ry}年にかけて、消費額は {cur.spend / mine.loc[first, 'spend']:.2f} 倍、1人あたりは {per[ry] / per[first]:.2f} 倍になりました。",
        f"1人あたりがいちばん高かったのは {per.idxmax()}年（{per.max():,.0f}円）です。",
    ], source="長野県「観光地利用者統計調査」（観光地消費額）")

# ---- 比べる ----
with ui.card():
    ui.block("県平均と比べる：1人あたりの消費額", f"{ry}年。調査対象の観光地での消費額÷延べ利用者数")
    pv = t.per_visit.where(t.spend > 0)
    ui.chart(compare.bars(cmp, pv, pref_per[ry], fmt=lambda x: f"{x:,.0f}円", pref_label="県全体"))
    ui.readout(compare.readout(cmp, pv, pref_per[ry], "1人あたりの消費額", fmt=lambda x: f"{x:,.0f}円", pref_label="県全体"),
               source=f"長野県「観光地利用者統計調査」（{ry}年）")

# ---- 2. 増減の内訳 ----
if ry - 1 in mine.index:
    with ui.card():
        ui.block("消費額の増減の内訳", f"{ry - 1}年→{ry}年の増減を「人数の変化」と「1人あたりの変化」に分けて表示")
        rows = []
        for y in [y for y in mine.index if y - 1 in mine.index][-6:]:
            s0, s1, v0, v1 = mine.loc[y - 1, "spend"], mine.loc[y, "spend"], mine.loc[y - 1, "total"], mine.loc[y, "total"]
            lv, lu = np.log(v1 / v0), np.log((s1 / v1) / (s0 / v0))
            sv = lv / (lv + lu) if (lv + lu) != 0 else 0.5
            rows.append({"year": y, "chg": s1 - s0, "by_v": (s1 - s0) * sv, "by_u": (s1 - s0) * (1 - sv)})
        dd = pd.DataFrame(rows).set_index("year")
        fig = go.Figure()
        for col, label, color in [("by_v", "人数の変化による分", charts.MAIN), ("by_u", "1人あたりの変化による分", charts.SECOND)]:
            fig.add_trace(go.Bar(x=[f"{y}年" for y in dd.index], y=dd[col] / 1e8, name=label, marker_color=color,
                                 marker_line={"color": "white", "width": 2}, hovertemplate=f"%{{x}} {label} %{{y:+,.2f}}億円<extra></extra>"))
        fig.add_trace(go.Scatter(x=[f"{y}年" for y in dd.index], y=dd.chg / 1e8, name="増減（合計）", mode="markers",
                                 marker={"color": "#333", "size": 10, "symbol": "diamond"}, hovertemplate="%{x} 合計 %{y:+,.2f}億円<extra></extra>"))
        fig.add_hline(y=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
        charts.layout(fig, height=340, barmode="relative", bargap=0.4, legend_traceorder="normal")
        fig.update_yaxes(title="前年からの増減（億円）")
        ui.chart(fig)
        r = dd.loc[ry]
        ui.readout([
            f"{ry}年の消費額の増減は {r.chg / 1e8:+,.2f}億円。人数の変化による分が {r.by_v / 1e8:+,.2f}億円、1人あたりの変化による分が {r.by_u / 1e8:+,.2f}億円です。",
            f"主な理由は **{'1人あたりの消費額' if abs(r.by_u) > abs(r.by_v) else '人数'}の変化** です。",
        ], source="長野県「観光地利用者統計調査」。増減は人数と1人あたりの変化の比率（対数）で分けています")

# ---- 3. 観光地別 ----
sp = data.riyousha_spots()
s = sp[(sp.municipality_code == code) & (sp.year == ry) & (sp.spend > 0)].set_index("spot")
if len(s):
    with ui.card():
        ui.block("観光地ごとの消費額", f"{ry}年。棒は消費額、（ ）内は1人あたり")
        b = s.sort_values("spend").assign(per=lambda x: x.spend / x.total)
        fig = go.Figure(go.Bar(
            y=b.index, x=b.spend / 1e8, orientation="h", marker_color=charts.MAIN,
            text=[f"{v / 1e8:,.1f}億円（{p:,.0f}円）" for v, p in zip(b.spend, b.per)], textposition="outside", cliponaxis=False,
            hovertemplate="%{y} %{x:,.2f}億円<extra></extra>",
        ))
        charts.layout(fig, height=max(240, 34 * len(b) + 70))
        fig.update_xaxes(title="億円", range=[0, b.spend.max() / 1e8 * 1.5])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
        ui.readout([
            f"消費額がいちばん多いのは **{b.spend.idxmax()}**（{yen(b.spend.max())}、調査対象の観光地の合計の {b.spend.max() / b.spend.sum():.0%}）です。",
            f"1人あたりがいちばん高いのは **{b.per.idxmax()}**（{b.per.max():,.0f}円）、低いのは **{b.per.idxmin()}**（{b.per.min():,.0f}円）です。",
        ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

ui.sources(["riyousha"])

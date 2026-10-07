import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, kouiki, muni, ui
from lib.charts import man

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}の観光地", "圏域にある県の調査対象の観光地のランキングと、種類の構成。", kicker="広域連携")
k, mem = kouiki.picker("spots")
LABEL = kouiki.label(k)

sp = data.riyousha_spots()
ry = int(sp.year.max())
ks = sp[sp.municipality_code.isin(mem)]
cur = ks[ks.year == ry].copy()
if cur.empty:
    st.info(f"選んだ市町村には、県の観光地利用者統計調査（{ry}年）の調査対象の観光地がありません。")
    st.stop()
prev = ks[ks.year == ry - 1].groupby("spot").total.sum()
y19 = ks[ks.year == 2019].groupby("spot").total.sum()
cur = cur.set_index("spot").assign(yoy=lambda x: x.total / prev.reindex(x.index) - 1, vs19=lambda x: x.total / y19.reindex(x.index) - 1)
top = cur.sort_values("total", ascending=False)

ui.insight(
    f"{ry}年、{LABEL}の県の調査対象の観光地は {len(cur)} か所。いちばん多いのは <b>{top.index[0]}</b>（{top.municipality.iloc[0]}、延べ {man(top.total.iloc[0])}）"
    + (f"、次いで {top.index[1]}（{top.municipality.iloc[1]}）" if len(top) > 1 else "") + "です。"
)

with ui.card():
    n = min(20, len(top))
    ui.block("観光地ランキング", f"{ry}年の延べ利用者数の上位{n}か所。（ ）内は前年比")
    b = top.head(n).iloc[::-1]
    fig = go.Figure(go.Bar(
        y=[f"{s}（{m}）" for s, m in zip(b.index, b.municipality)], x=b.total / 1e4, orientation="h", marker_color=charts.MAIN,
        text=[f"{v / 1e4:,.1f}万人" + ("" if pd.isna(c) else f"（{c:+.0%}）") for v, c in zip(b.total, b.yoy)],
        textposition="outside", cliponaxis=False, customdata=b.category, hovertemplate="<b>%{y}</b>（%{customdata}）%{x:,.1f}万人<extra></extra>",
    ))
    charts.layout(fig, height=max(260, 30 * len(b) + 70))
    fig.update_xaxes(title="延べ利用者数（万人）", range=[0, b.total.max() / 1e4 * 1.4])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    g = cur.dropna(subset=["yoy"])
    g = g[g.total >= 10_000]
    ui.readout([
        f"市町村ごとの観光地の数: " + "、".join(f"{m} {c}か所" for m, c in cur.municipality.value_counts().items()) + "。",
        (f"1万人以上の観光地で前年から伸びが大きいのは **{g.yoy.idxmax()}**（{g.yoy.max():+.0%}）"
         + (f"、減少が大きいのは **{g.yoy.idxmin()}**（{g.yoy.min():+.0%}）です。" if g.yoy.min() < 0 else "で、どこも前年を上回りました。")) if len(g) >= 2 else "",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）。スキー場は調査の対象外です")

with ui.card():
    ui.block("観光地の種類", f"{ry}年。延べ利用者数に占める割合を県全体と比較")
    pref = sp[sp.year == ry].groupby("category").total.sum()
    mc = cur.groupby("category").total.sum()
    cats = pref.sort_values(ascending=False).index
    fig = go.Figure()
    for vv, label, color in [(mc.reindex(cats).fillna(0) / mc.sum(), LABEL, charts.MAIN), (pref.reindex(cats) / pref.sum(), "県全体", charts.CONTEXT)]:
        fig.add_trace(go.Bar(x=list(cats), y=vv.values, name=label, marker_color=color, text=[f"{x:.0%}" for x in vv.values],
                             textposition="outside", hovertemplate=f"{label} %{{x}}: %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=320, barmode="group", bargap=0.3)
    fig.update_yaxes(tickformat=".0%", range=[0, max(mc.max() / mc.sum(), pref.max() / pref.sum()) * 1.25])
    ui.chart(fig)
    d = (mc.reindex(cats).fillna(0) / mc.sum() - pref.reindex(cats) / pref.sum()).sort_values()
    ui.readout([
        f"{LABEL}でいちばん多いのは **{mc.idxmax()}**（{mc.max() / mc.sum():.0%}）です。",
        f"県全体と比べて割合が高いのは **{d.index[-1]}**（{d.iloc[-1] * 100:+.0f}ポイント）、低いのは **{d.index[0]}**（{d.iloc[0] * 100:+.0f}ポイント）です。",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

with ui.card():
    ui.block("コロナ前（2019年）からの回復", f"{ry}年の延べ利用者数の2019年比。両方の年にある観光地だけ")
    both = cur.dropna(subset=["vs19"])
    both = both[y19.reindex(both.index) > 0]
    if len(both):
        bm = both.groupby("municipality").total.sum() / y19.reindex(both.index).groupby(both.municipality).sum() - 1
        bm = bm.sort_values()
        fig = go.Figure(go.Bar(y=bm.index, x=bm.values, orientation="h", marker_color=[charts.MAIN if v >= 0 else charts.SECOND for v in bm],
                               text=[f"{v:+.0%}" for v in bm], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} 2019年比 %{x:+.1%}<extra></extra>"))
        lim = max(bm.abs().max() * 1.4, 0.15)
        charts.layout(fig, height=max(220, 34 * len(bm) + 70))
        fig.update_xaxes(tickformat="+.0%", range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
        allr = both.total.sum() / y19.reindex(both.index).sum() - 1
        ui.readout([
            f"圏域全体（同じ観光地の合計）は2019年比 {allr:+.0%} です。",
            f"2019年を上回っている市町村: {'・'.join(bm[bm > 0].index) or 'なし'}。",
        ], source="長野県「観光地利用者統計調査」")

ui.sources(["riyousha"])

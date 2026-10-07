import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, kouiki, muni, ui
from lib.charts import man

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}を他の広域と比べる", "10広域の中での位置と、県平均（10広域の平均）・県全体との比較。", kicker="広域連携")
k, mem = kouiki.picker("compare")
LABEL = kouiki.label(k)
muni.require_digital()

t = muni.vtable()
ly, Y, SPAN = t.attrs["year"], t.attrs["Y"], t.attrs["span"]
v = muni.visitors()
me = k if k != kouiki.CUSTOM else "_custom"
groups = {kk: kouiki.members(kk) for kk in kouiki.names()}
names = {kk: f"{kk}広域" for kk in groups}
if me == "_custom":
    groups["_custom"], names["_custom"] = mem, "選んだ圏域"
T = pd.DataFrame({g: kouiki.stats(c) for g, c in groups.items()}).T.astype(float)
ten = T.drop(index="_custom", errors="ignore")
pop = muni.population()
PREF = {"visitors": ten.visitors.mean(), "now": ten.now.mean(),
        "per_resident": t.visitors.sum() / pop.reindex(t.index)[t.visitors.notna()].sum(),
        "yoy": ten.visitors.sum() / (ten.visitors / (1 + ten.yoy)).sum() - 1,
        "now_yoy": ten.now.sum() / (ten.now / (1 + ten.now_yoy)).sum() - 1}
mine = T.loc[me]
sel = compare.Sel(me=me, me_name=names[me], names=names)
SRC = f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成、総務省「国勢調査」（2020年）。{kouiki.SUM_NOTE}"


def rank(col):
    r = ten[col].rank(ascending=False)
    return f"{int(r[me])}位／10" if me in r.index and pd.notna(r[me]) else "—"


ui.insight(
    f"{ly}年の{names[me]}の観光来訪者数（市町村の合計）は <b>{man(mine.visitors)}</b>"
    + (f"で、10広域の <b>{rank('visitors')}</b>" if me != "_custom" else "")
    + f"。住民1人あたりでは {mine.per_resident:,.0f}人（県全体 {PREF['per_resident']:,.0f}人）"
    + (f"で {rank('per_resident')}" if me != "_custom" else "") + "です。"
)

METRICS = [
    ("visitors", f"観光来訪者数（{ly}年）", man, "県平均"),
    ("now", f"観光来訪者数（{Y}年{SPAN}）", man, "県平均"),
    ("per_resident", "住民1人あたりの来訪者", lambda x: f"{x:,.0f}人", "県全体"),
]
if t.attrs["has_yoy"]:
    METRICS.append(("yoy", f"前年比（{ly}年）", lambda x: charts.signed(x, 1), "県全体"))
if t.attrs["has_prev"]:
    METRICS.append(("now_yoy", f"前年比（{Y}年{SPAN}）", lambda x: charts.signed(x, 1), "県全体"))

with ui.card():
    ui.block("県平均と比べる", "県平均は10広域の平均、県全体は77市町村の合計で計算")
    cols = st.columns(len(METRICS))
    for c, (col, label, f, pl) in zip(cols, METRICS):
        with c:
            ui.kpi(label, f(mine[col]), (f"10広域で {rank(col)}／" if me != "_custom" else "") + f"{pl} {f(PREF[col])}")
    c1, c2 = st.columns(2)
    with c1:
        ui.chart(compare.bars(sel, T.visitors, PREF["visitors"], fmt=man, title=f"観光来訪者数（{ly}年）"))
    with c2:
        ui.chart(compare.bars(sel, T.per_resident, PREF["per_resident"], fmt=lambda x: f"{x:,.0f}人", title="住民1人あたりの来訪者",
                              pref_label="県全体"))
    ui.readout(compare.readout(sel, T.visitors, PREF["visitors"], "観光来訪者数", fmt=man, higher="多い", lower="少ない")
               + compare.readout(sel, T.per_resident, PREF["per_resident"], "住民1人あたりの来訪者", fmt=lambda x: f"{x:,.0f}人",
                                 higher="多い", lower="少ない", pref_label="県全体")
               + ([] if t.attrs["has_yoy"] else [muni.NOTE_2025]),
               source=SRC)

with ui.card():
    ui.block("10広域の観光来訪者数", f"{ly}年。市町村の合計")
    b = T.sort_values("visitors")
    fig = go.Figure(go.Bar(y=[names[g] for g in b.index], x=b.visitors / 1e4, orientation="h",
                           marker_color=[charts.MAIN if g == me else charts.CONTEXT for g in b.index],
                           text=[man(x) for x in b.visitors], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y} %{x:,.1f}万人<extra></extra>"))
    fig.add_vline(x=PREF["visitors"] / 1e4, line={"color": compare.PREF_COLOR, "dash": "dot", "width": 2})
    fig.add_annotation(x=PREF["visitors"] / 1e4, y=1, yref="paper", text=f"県平均 {man(PREF['visitors'])}", showarrow=False, yanchor="bottom")
    charts.layout(fig, height=max(320, 34 * len(b) + 80))
    fig.update_xaxes(title="万人", range=[0, b.visitors.max() / 1e4 * 1.3])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    above = [names[g] for g in ten.index if ten.loc[g, "visitors"] > PREF["visitors"]]
    ui.readout([
        f"いちばん多いのは **{names[ten.visitors.idxmax()]}**（{man(ten.visitors.max())}）、いちばん少ないのは **{names[ten.visitors.idxmin()]}**（{man(ten.visitors.min())}）です。",
        f"県平均（10広域の平均）を上回っているのは {'・'.join(above)} です。",
    ], source=SRC)

with ui.card():
    ui.block("10広域の一覧", f"{ly}年と{Y}年{SPAN}")
    tb = T.sort_values("visitors", ascending=False)
    cols = {"広域": [names[g] for g in tb.index], "市町村数": [len(groups[g]) for g in tb.index], f"{ly}年": tb.visitors.round(),
            f"{Y}年{SPAN}": tb.now.round(), "住民1人あたり": tb.per_resident.round(1)}
    if t.attrs["has_yoy"]:
        cols["前年比"] = tb.yoy
    st.dataframe(pd.DataFrame(cols), hide_index=True, use_container_width=True, column_config={
        f"{ly}年": st.column_config.NumberColumn(format="localized"), f"{Y}年{SPAN}": st.column_config.NumberColumn(format="localized"),
        "前年比": st.column_config.NumberColumn(format="percent"),
    })
    st.caption(kouiki.SUM_NOTE + "。")

ui.sources(["digital", "population"])

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, kouiki, muni, ui
from lib.charts import man

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}を他の広域と比べる", "10広域の中での位置。比べる広域を選び、県平均（10広域の平均）とも比べられます。", kicker="広域連携")
k, mem = kouiki.picker("compare")
LABEL = kouiki.label(k)

muni.require_digital()
# 比べる単位は広域。自由に組んだ圏域も「選んだ圏域」として並べる
kt = kouiki.table()
me = k if k != kouiki.CUSTOM else "_custom"
if me == "_custom":
    kt = pd.concat([pd.DataFrame({"name": ["選んだ圏域"], "kouiki": ["長野県の10広域"]}, index=["_custom"]), kt])
cmp = compare.picker(me, kt, "kcompare", unit="広域")

v = muni.visitors()
y = muni.yearly()
t = muni.vtable()
ly, Y, M = t.attrs["year"], t.attrs["Y"], t.attrs["M"]
groups = {kk: kouiki.members(kk) for kk in kouiki.names()}
if me == "_custom":
    groups["_custom"] = mem
pop = muni.population()


def agg(codes):
    codes = [c for c in codes if c in v]
    a = y[codes].sum(axis=1)
    return {
        "visitors": a[ly], "yoy": a[ly] / a[ly - 1] - 1 if ly - 1 in a.index else None,
        "ytd": muni.ytd(Y, M)[codes].sum(), "ytd_yoy": muni.ytd(Y, M)[codes].sum() / muni.ytd(Y - 1, M)[codes].sum() - 1,
        "per_resident": a[ly] / pop.reindex(codes).sum(), "n": len(codes),
    }


T = pd.DataFrame({g: agg(c) for g, c in groups.items()}).T.astype(float)
ten = T.drop(index="_custom", errors="ignore")
PREF = {"visitors": ten.visitors.mean(), "yoy": y.loc[ly].sum() / y.loc[ly - 1].sum() - 1, "ytd": ten.ytd.mean(),
        "ytd_yoy": t.ytd.sum() / muni.ytd(Y - 1, M).sum() - 1, "per_resident": y.loc[ly].sum() / pop.sum()}
mine = T.loc[me]

def rank(col):
    r = ten[col].rank(ascending=False)
    return f"{int(r[me])}位／10" if me in r.index else "—"

ui.insight(
    f"{ly}年の{LABEL}の観光来訪者数（市町村の合計）は <b>{man(mine.visitors)}</b>"
    + (f"で10広域の <b>{rank('visitors')}</b>" if me != "_custom" else "")
    + f"、前年比は {mine.yoy:+.0%}（県全体 {PREF['yoy']:+.0%}）。{Y}年1〜{M}月は前年の同じ時期より {mine.ytd_yoy:+.0%} です。"
)

METRICS = [
    ("visitors", f"観光来訪者数（{ly}年）", man, "県平均"),
    ("yoy", f"前年比（{ly}年）", lambda x: charts.signed(x, 1), "県全体"),
    ("ytd_yoy", f"{Y}年1〜{M}月の伸び", lambda x: charts.signed(x, 1), "県全体"),
    ("per_resident", "住民1人あたりの来訪者", lambda x: f"{x:,.0f}人", "県全体"),
]

with ui.card():
    ui.block("比べる：数字を並べる", "選んだ広域と県平均（10広域の平均）・県全体")
    cols = st.columns(4)
    for c, (col, label, f, pl) in zip(cols, METRICS):
        with c:
            ui.kpi(label, f(mine[col]), (f"10広域で {rank(col)}／" if me != "_custom" else "") + f"{pl} {f(PREF[col])}")
    c1, c2 = st.columns(2)
    for c, (col, label, f, pl) in zip([c1, c2, c1, c2], METRICS):
        with c:
            ui.chart(compare.bars(cmp, T[col], PREF[col], fmt=f, title=label, pref_label=pl,
                                  tickformat="+.0%" if "yoy" in col else None))
    compare.hint(cmp, "広域")
    ui.readout(compare.readout(cmp, T.ytd_yoy, PREF["ytd_yoy"], f"{Y}年1〜{M}月の伸び", fmt=charts.signed,
                               higher="大きい", lower="小さい", pref_label="県全体")
               + compare.readout(cmp, T.per_resident, PREF["per_resident"], "住民1人あたりの来訪者", fmt=lambda x: f"{x:,.0f}人",
                                 higher="多い", lower="少ない", pref_label="県全体"),
               source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成、総務省「国勢調査」（2020年）。{kouiki.SUM_NOTE}")

with ui.card():
    ui.block("比べる：月ごとの動き", "前年同月比。選んだ広域と県全体")
    mon = pd.DataFrame({g: v[[c for c in cs if c in v]].sum(axis=1) for g, cs in groups.items()})
    yoy = (mon / mon.shift(12) - 1)
    yoy = yoy[yoy.index >= pd.Timestamp(Y - 1, 1, 1)]
    ptot = v.sum(axis=1)
    pref_yoy = (ptot / ptot.shift(12) - 1).reindex(yoy.index)
    fig = compare.lines(cmp, yoy[[c for c in cmp.all if c in yoy]], pref=pref_yoy, hover="%{y:+.0%}", pref_label="県全体")
    fig.update_yaxes(tickformat="+.0%")
    fig.update_xaxes(tickformat="%Y年%-m月")
    fig.add_hline(y=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
    ui.chart(fig)
    last = yoy.iloc[-1].reindex(cmp.all).dropna()
    ui.readout([
        f"{Y}年{M}月の前年同月比: " + "、".join(f"{cmp.label(c)} {x:+.0%}" for c, x in last.items()) + f"（県全体 {pref_yoy.iloc[-1]:+.0%}）。",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

with ui.card():
    ui.block("10広域の一覧", f"{ly}年と{Y}年1〜{M}月")
    tb = T.sort_values("visitors", ascending=False)
    st.dataframe(pd.DataFrame({
        "広域": [kt.loc[i, "name"] for i in tb.index], "市町村数": tb.n.astype(int), f"{ly}年": tb.visitors.round(),
        "前年比": tb.yoy, f"{Y}年1〜{M}月の伸び": tb.ytd_yoy, "住民1人あたり": tb.per_resident.round(1),
    }), hide_index=True, use_container_width=True, column_config={
        f"{ly}年": st.column_config.NumberColumn(format="localized"), "前年比": st.column_config.NumberColumn(format="percent"),
        f"{Y}年1〜{M}月の伸び": st.column_config.NumberColumn(format="percent"),
    })
    st.caption(kouiki.SUM_NOTE + "。")

ui.sources(["digital", "population"])

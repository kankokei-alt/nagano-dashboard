import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, muni, ui
from lib.charts import man, updown

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}の観光地", "どの観光地に人が集まり、伸びているか。観光地ごとの推移も見られます。", kicker="市町村")
code = muni.picker("spots")

sp = data.riyousha_spots()
mine = sp[sp.municipality_code == code]
if mine.empty:
    st.info(f"{NAME}には、県の観光地利用者統計調査の調査対象の観光地がありません。")
    st.stop()
ry = int(mine.year.max())
cur = mine[mine.year == ry].set_index("spot")
prv = mine[mine.year == ry - 1].groupby("spot").total.sum()
y19 = mine[mine.year == 2019].groupby("spot").total.sum()
cur = cur.assign(yoy=cur.total / prv.reindex(cur.index) - 1, vs19=cur.total / y19.reindex(cur.index) - 1)
top = cur.sort_values("total", ascending=False)

ui.insight(
    f"{ry}年、{NAME}の調査対象の観光地は {len(cur)} か所。いちばん多いのは <b>{top.index[0]}</b>（{man(top.total.iloc[0])}、市町村全体の {top.total.iloc[0] / cur.total.sum():.0%}）"
    + (f"、次いで {top.index[1]}（{man(top.total.iloc[1])}）" if len(top) > 1 else "") + "です。"
)

# ---- 1. ランキング ----
with ui.card():
    ui.block("観光地ランキング", f"{ry}年の延べ利用者数。（ ）内は前年比")
    b = top.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=b.index, x=b.total / 1e4, orientation="h", marker_color=charts.MAIN,
        text=[f"{v / 1e4:,.1f}万人" + ("" if pd.isna(c) else f"（{c:+.0%}）") for v, c in zip(b.total, b.yoy)],
        textposition="outside", cliponaxis=False, customdata=b.category,
        hovertemplate="<b>%{y}</b>（%{customdata}）%{x:,.1f}万人<extra></extra>",
    ))
    charts.layout(fig, height=max(240, 34 * len(b) + 70))
    fig.update_xaxes(title="万人", range=[0, b.total.max() / 1e4 * 1.4])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    g = cur.dropna(subset=["yoy"])
    ui.readout([
        f"上位3か所で市町村全体の {top.total.iloc[:3].sum() / cur.total.sum():.0%} を占めます。" if len(top) >= 3 else "",
        (f"前年からの伸びが大きいのは **{g.yoy.idxmax()}**（{g.yoy.max():+.0%}）、減少が大きいのは **{g.yoy.idxmin()}**（{g.yoy.min():+.0%}）です。" if len(g) >= 2 else ""),
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

# ---- 2. 推移 ----
with ui.card():
    ui.block("観光地ごとの推移", "年ごとの延べ利用者数。比べたい観光地を選べます")
    hist = data.riyousha_history()
    hist = hist[hist.municipality_code == code]
    names = list(top.index)
    pick = st.multiselect("観光地（4つまで）", names, default=names[:min(4, len(names))], key=f"spots_{code}", max_selections=4)
    tr = hist[hist.spot.isin(pick)].pivot_table(index="year", columns="spot", values="visitors")
    fig = go.Figure()
    palette = [charts.MAIN, charts.SECOND, charts.THIRD, charts.CONTEXT]
    ends = charts.spread({s: tr[s].dropna().iloc[-1] / 1e4 for s in pick if s in tr},
                         gap=(tr.max().max() / 1e4) * 0.06 if len(tr) else 1)
    for i, s in enumerate(pick):
        if s not in tr:
            continue
        v = tr[s].dropna()
        fig.add_trace(go.Scatter(x=v.index, y=v / 1e4, name=s, mode="lines+markers", line={"color": palette[i % len(palette)], "width": 2.5},
                                 hovertemplate=f"{s} %{{x}}年 %{{y:,.1f}}万人<extra></extra>"))
        fig.add_annotation(x=v.index[-1], y=ends[s], text=s, showarrow=False, xanchor="left", xshift=8, font={"size": 11})
    charts.layout(fig, height=360, hovermode="x unified")
    fig.update_yaxes(title="万人", rangemode="tozero")
    fig.update_xaxes(dtick=1, range=[tr.index.min() - 0.5, tr.index.max() + 2.5] if len(tr) else None)
    ui.chart(fig)
    pts = []
    for s in pick:
        if s in tr and 2019 in tr.index and pd.notna(tr.loc[2019, s]) and tr.loc[2019, s] > 0:
            pts.append(f"{s}: 2019年比 {tr[s].dropna().iloc[-1] / tr.loc[2019, s] - 1:+.0%}")
    ui.readout(["選んだ観光地の2019年からの変化: " + "、".join(pts) + "。"] if pts else [],
               source="長野県「観光地利用者統計調査」（観光地別の年次推移）")

# ---- 3. コロナ前からの変化 ----
g19 = cur.dropna(subset=["vs19"]).sort_values("vs19")
if len(g19) >= 2:
    with ui.card():
        ui.block("コロナ前（2019年）からの変化", f"観光地ごとの{ry}年の延べ利用者数の2019年比")
        fig = go.Figure(go.Bar(
            y=g19.index, x=g19.vs19, orientation="h",
            marker_color=[charts.MAIN if v >= 0 else charts.SECOND for v in g19.vs19],
            text=[f"{v:+.0%}" for v in g19.vs19], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: 2019年比 %{x:+.1%}<extra></extra>",
        ))
        lim = max(g19.vs19.abs().max() * 1.35, 0.2)
        charts.layout(fig, height=max(240, 32 * len(g19) + 70))
        fig.update_xaxes(tickformat="+.0%", range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
        ui.readout([
            f"2019年を上回っているのは {(g19.vs19 > 0).sum()} か所、下回っているのは {(g19.vs19 < 0).sum()} か所です。",
            f"いちばん伸びたのは **{g19.index[-1]}**（{g19.vs19.iloc[-1]:+.0%}）、いちばん減ったのは **{g19.index[0]}**（{g19.vs19.iloc[0]:+.0%}）です。",
        ], source="長野県「観光地利用者統計調査」")

# ---- 4. 種類 ----
with ui.card():
    ui.block("観光地の種類", f"{ry}年。延べ利用者数に占める割合を県全体と比較")
    pref = sp[sp.year == ry].groupby("category").total.sum()
    mc = cur.groupby("category").total.sum()
    cats = pref.index
    fig = go.Figure()
    for v, label, color in [(mc.reindex(cats).fillna(0) / mc.sum(), NAME, charts.MAIN), (pref / pref.sum(), "県全体", charts.CONTEXT)]:
        fig.add_trace(go.Bar(x=list(cats), y=v.values, name=label, marker_color=color, text=[f"{x:.0%}" for x in v.values],
                             textposition="outside", hovertemplate=f"{label} %{{x}}: %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=300, barmode="group", bargap=0.3)
    fig.update_yaxes(tickformat=".0%", range=[0, 1.1])
    ui.chart(fig)
    ui.readout([
        f"{NAME}でいちばん多いのは **{mc.idxmax()}**（{mc.max() / mc.sum():.0%}）です。",
        "観光地ごとの種類: " + "、".join(f"{s}（{c}）" for s, c in top.category.items()) + "。",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

with ui.card():
    ui.block("観光地ごとの数字", f"{ry}年")
    tbl = top.reset_index()[["spot", "category", "total", "yoy", "vs19", "kengai", "shukuhaku", "spend"]]
    tbl = tbl.assign(kengai=tbl.kengai / tbl.total, shukuhaku=tbl.shukuhaku / tbl.total, per=tbl.spend / tbl.total)
    st.dataframe(tbl, hide_index=True, use_container_width=True, column_config={
        "spot": "観光地", "category": "種類",
        "total": st.column_config.NumberColumn("延べ利用者数（人）", format="localized"),
        "yoy": st.column_config.NumberColumn("前年比", format="percent"),
        "vs19": st.column_config.NumberColumn("2019年比", format="percent"),
        "kengai": st.column_config.NumberColumn("県外の人の割合", format="percent"),
        "shukuhaku": st.column_config.NumberColumn("泊まりの人の割合", format="percent"),
        "spend": st.column_config.NumberColumn("観光地での消費額（円）", format="localized"),
        "per": st.column_config.NumberColumn("1人あたり（円）", format="localized"),
    })
    st.download_button("CSVでダウンロード", tbl.to_csv(index=False).encode("utf-8-sig"), file_name=f"{NAME}_観光地_{ry}.csv", mime="text/csv")

ui.sources(["riyousha"])

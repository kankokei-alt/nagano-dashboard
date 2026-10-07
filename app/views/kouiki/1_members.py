import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, kouiki, muni, ui

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}の市町村の役割", "圏域の中で、人が集まる市町村と、住民の数に比べて人が多く訪れる市町村。", kicker="広域連携")
k, mem = kouiki.picker("members")
LABEL = kouiki.label(k)
muni.require_digital()

t = muni.vtable()
ly, Y, SPAN = t.attrs["year"], t.attrs["Y"], t.attrs["span"]
mt = t.reindex(mem).dropna(subset=["visitors"])
if len(mt) < 2:
    st.info("人数が公表されている市町村が2つ以上あると、圏域の中の役割を比べられます。")
    st.stop()
tot = mt.visitors.sum()
mt = mt.assign(kshare=mt.visitors / tot, nshare=mt.now / mt.now.sum())
big = mt.sort_values("visitors", ascending=False)
pr_k = tot / muni.population().reindex(mt.index).sum()
SRC = f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成。{kouiki.SUM_NOTE}"

ui.insight(
    f"{ly}年の{LABEL}では、<b>{big.name.iloc[0]}</b> が圏域の {big.kshare.iloc[0]:.0%} を占めます。"
    f"住民の数に比べて人が多く訪れるのは <b>{mt.loc[mt.per_resident.idxmax(), 'name']}</b>（住民1人あたり {mt.per_resident.max():,.0f}人）です。"
)

# ---- 1. 役割（割合×住民1人あたり） ----
with ui.card():
    ui.block("圏域の中の役割", f"{ly}年。横：圏域に占める割合、縦：住民1人あたりの来訪者")
    fig = go.Figure(go.Scatter(
        x=mt.kshare, y=mt.per_resident, mode="markers+text", text=mt.name, textposition="top center",
        marker={"size": 16, "color": charts.MAIN, "opacity": .8, "line": {"color": "white", "width": 2}},
        customdata=mt.visitors / 1e4,
        hovertemplate="<b>%{text}</b><br>圏域の %{x:.0%}・住民1人あたり %{y:,.0f}人<br>%{customdata:,.1f}万人<extra></extra>",
    ))
    fig.add_hline(y=pr_k, line={"color": charts.CONTEXT, "dash": "dot"})
    fig.add_annotation(x=1, xref="paper", y=pr_k, yref="y", text=f"圏域全体 {pr_k:,.0f}人", showarrow=False, yanchor="bottom", xanchor="right")
    fig.add_vline(x=1 / len(mt), line={"color": charts.CONTEXT, "dash": "dot"})
    charts.layout(fig, height=420, showlegend=False)
    fig.update_xaxes(title="圏域に占める割合", tickformat=".0%", rangemode="tozero")
    fig.update_yaxes(title="住民1人あたりの来訪者（人）", rangemode="tozero")
    ui.chart(fig)
    hub = mt[mt.kshare >= 1 / len(mt)]
    dest = mt[(mt.kshare < 1 / len(mt)) & (mt.per_resident > pr_k)]
    ui.readout([
        f"人が集まる中心（圏域の平均以上の割合、縦の点線より右）: {'・'.join(hub.name)}。",
        f"規模は小さいが、住民の数に比べて人が多く訪れる市町村: {'・'.join(dest.name)}。" if len(dest) else "",
        "住民1人あたりの来訪者が多いほど、地域の中で観光の比重が大きいと読めます。",
    ], source=f"{SRC}、総務省「国勢調査」（2020年）")

# ---- 2. 今年の割合 ----
with ui.card():
    ui.block("圏域の中の割合", f"{ly}年と{Y}年{SPAN}")
    order = big.index[::-1]
    fig = go.Figure()
    for col, label, color in [("kshare", f"{ly}年", charts.CONTEXT), ("nshare", f"{Y}年{SPAN}", charts.MAIN)]:
        fig.add_trace(go.Bar(y=mt.loc[order, "name"], x=mt.loc[order, col], orientation="h", name=label, marker_color=color,
                             text=[f"{x:.0%}" if pd.notna(x) else "" for x in mt.loc[order, col]], textposition="outside", cliponaxis=False,
                             hovertemplate=f"%{{y}} {label} 圏域の %{{x:.1%}}<extra></extra>"))
    charts.layout(fig, height=max(260, 46 * len(mt) + 80), barmode="group", bargap=0.25, legend_traceorder="reversed")
    fig.update_xaxes(tickformat=".0%", range=[0, max(mt.kshare.max(), mt.nshare.max()) * 1.3])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    d = (mt.nshare - mt.kshare).dropna().sort_values()
    ui.readout([
        f"{Y}年{SPAN}は {ly}年の1年間より、**{mt.loc[d.index[-1], 'name']}** の割合が大きく（{d.iloc[-1] * 100:+.1f}ポイント）、"
        f"**{mt.loc[d.index[0], 'name']}** の割合が小さく（{d.iloc[0] * 100:+.1f}ポイント）なっています。" if len(d) >= 2 else "",
        f"{SPAN}だけの割合なので、冬に人が集まる市町村は小さめに出ます。",
    ], source=SRC)

with ui.card():
    ui.block("市町村ごとの数字", f"{ly}年と{Y}年{SPAN}")
    tbl = big
    cols = {"市町村": tbl.name, f"{ly}年": tbl.visitors.round(), "圏域の割合": tbl.kshare,
            f"{Y}年{SPAN}": tbl.now.round(), "住民1人あたり": tbl.per_resident.round(1)}
    if t.attrs["has_yoy"]:
        cols["前年比"] = tbl.yoy
    st.dataframe(pd.DataFrame(cols), hide_index=True, use_container_width=True, column_config={
        f"{ly}年": st.column_config.NumberColumn(format="localized"), f"{Y}年{SPAN}": st.column_config.NumberColumn(format="localized"),
        "圏域の割合": st.column_config.NumberColumn(format="percent"), "前年比": st.column_config.NumberColumn(format="percent"),
    })
    miss = [muni.name(c) for c in mem if c not in mt.index]
    if miss:
        st.caption(f"{'・'.join(miss)}は、人数が少なく公表されていない月があるため表に入れていません。")

ui.sources(["digital", "population"])

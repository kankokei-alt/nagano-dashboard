import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, kouiki, muni, ui
from lib.charts import man, updown

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}の市町村の役割", "圏域の中で、人が集まる市町村と伸びている市町村。", kicker="広域連携")
k, mem = kouiki.picker("members")
LABEL = kouiki.label(k)

t = muni.vtable()
ly, Y, M = t.attrs["year"], t.attrs["Y"], t.attrs["M"]
mt = t.reindex(mem).dropna(subset=["visitors"])
if len(mt) < 2:
    st.info("2つ以上の市町村を選ぶと、圏域の中の役割を比べられます。")
    st.stop()
tot = mt.visitors.sum()
mt = mt.assign(kshare=mt.visitors / tot)
k_yoy = tot / muni.yearly().loc[ly - 1, mt.index].sum() - 1
big = mt.sort_values("visitors", ascending=False)

ui.insight(
    f"{ly}年の{LABEL}では、<b>{big.name.iloc[0]}</b> が圏域の {big.kshare.iloc[0]:.0%} を占めます。"
    f"圏域全体の伸び（{k_yoy:+.0%}）より大きく伸びたのは {'・'.join(mt[mt.yoy > k_yoy].name) or 'ありません'}。"
)

# ---- 1. 役割の地図（割合×伸び） ----
with ui.card():
    ui.block("圏域の中の役割", f"{ly}年。横：圏域に占める割合、縦：前年比、円の大きさ：住民1人あたりの来訪者")
    fig = go.Figure(go.Scatter(
        x=mt.kshare, y=mt.yoy, mode="markers+text", text=mt.name, textposition="top center",
        marker={"size": (mt.per_resident / mt.per_resident.max()) ** 0.5 * 44 + 8, "color": charts.MAIN, "opacity": .75,
                "line": {"color": "white", "width": 2}},
        customdata=list(zip(mt.visitors / 1e4, mt.per_resident)),
        hovertemplate="<b>%{text}</b><br>圏域の %{x:.0%}・前年比 %{y:+.0%}<br>%{customdata[0]:,.1f}万人・住民1人あたり %{customdata[1]:,.0f}人<extra></extra>",
    ))
    fig.add_hline(y=k_yoy, line={"color": charts.CONTEXT, "dash": "dot"})
    fig.add_annotation(x=1, xref="paper", y=k_yoy, text=f"圏域全体 {k_yoy:+.0%}", showarrow=False, yanchor="bottom", xanchor="right")
    charts.layout(fig, height=420, showlegend=False)
    fig.update_xaxes(title="圏域に占める割合", tickformat=".0%", rangemode="tozero")
    fig.update_yaxes(title="前年比", tickformat="+.0%")
    ui.chart(fig)
    hub = mt[mt.kshare >= 1 / len(mt)]
    grow = mt[(mt.kshare < 1 / len(mt)) & (mt.yoy > k_yoy)]
    ui.readout([
        f"人が集まる中心（圏域の平均以上の割合）: {'・'.join(hub.name)}。",
        f"規模は小さいが圏域全体より伸びている市町村: {'・'.join(grow.name)}。" if len(grow) else "規模の小さい市町村で、圏域全体より伸びているところはありません。",
        f"住民1人あたりの来訪者がいちばん多いのは **{mt.loc[mt.per_resident.idxmax(), 'name']}**（{mt.per_resident.max():,.0f}人）です。",
    ], source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成、総務省「国勢調査」（2020年）。{kouiki.SUM_NOTE}")

# ---- 2. 年ごとの割合 ----
with ui.card():
    ui.block("圏域の中の割合の移り変わり", "年ごと。100%積み上げ")
    y = muni.yearly()[list(mt.index)]
    sh = y.div(y.sum(axis=1), axis=0)
    order = big.index
    pal = charts.SEQ[::-1] + ["#dfe9f6"] * 20
    fig = go.Figure()
    for i, c in enumerate(order):
        fig.add_trace(go.Bar(x=sh.index, y=sh[c], name=mt.loc[c, "name"], marker_color=pal[i % len(pal)] if i < 6 else charts.CONTEXT,
                             marker_line={"color": "white", "width": 1},
                             text=[f"{v:.0%}" if v >= 0.06 else "" for v in sh[c]], textposition="inside",
                             hovertemplate=f"{mt.loc[c, 'name']} %{{x}}年 %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=360, barmode="stack", bargap=0.3, legend_traceorder="normal")
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    fig.update_xaxes(dtick=1)
    ui.chart(fig)
    d = (sh.iloc[-1] - sh.iloc[0]).sort_values()
    ui.readout([
        f"{sh.index[0]}年から{sh.index[-1]}年で割合がいちばん増えたのは **{mt.loc[d.index[-1], 'name']}**（{d.iloc[-1] * 100:+.1f}ポイント）、"
        f"いちばん減ったのは **{mt.loc[d.index[0], 'name']}**（{d.iloc[0] * 100:+.1f}ポイント）です。",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

# ---- 3. 今年の伸び ----
with ui.card():
    ui.block("今年の伸び", f"{Y}年1〜{M}月の累計の前年比")
    b = mt.sort_values("ytd_yoy")
    k_ytd = muni.ytd(Y, M)[mt.index].sum() / muni.ytd(Y - 1, M)[mt.index].sum() - 1
    fig = go.Figure(go.Bar(y=b.name, x=b.ytd_yoy, orientation="h",
                           marker_color=[charts.MAIN if v >= 0 else charts.SECOND for v in b.ytd_yoy],
                           text=[f"{v:+.0%}（{man(n)}）" for v, n in zip(b.ytd_yoy, b.ytd)], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y} %{x:+.1%}<extra></extra>"))
    fig.add_vline(x=k_ytd, line={"color": charts.CONTEXT, "dash": "dot", "width": 2})
    lim = max(b.ytd_yoy.abs().max() * 1.6, 0.1)
    charts.layout(fig, height=max(240, 34 * len(b) + 70))
    fig.update_xaxes(tickformat="+.0%", range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    ui.readout([
        f"圏域全体は {updown(k_ytd)}（点線）。前年を上回っているのは {(b.ytd_yoy > 0).sum()}／{len(b)}市町村です。",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

with ui.card():
    ui.block("市町村ごとの数字", f"{ly}年と{Y}年1〜{M}月")
    tbl = mt.sort_values("visitors", ascending=False)
    st.dataframe(pd.DataFrame({
        "市町村": tbl.name, f"{ly}年": tbl.visitors.round(), "圏域の割合": tbl.kshare, "前年比": tbl.yoy,
        f"{Y}年1〜{M}月": tbl.ytd.round(), "1〜{}月の前年比".format(M): tbl.ytd_yoy, "住民1人あたり": tbl.per_resident.round(1),
    }), hide_index=True, use_container_width=True, column_config={
        f"{ly}年": st.column_config.NumberColumn(format="localized"), f"{Y}年1〜{M}月": st.column_config.NumberColumn(format="localized"),
        "圏域の割合": st.column_config.NumberColumn(format="percent"), "前年比": st.column_config.NumberColumn(format="percent"),
        "1〜{}月の前年比".format(M): st.column_config.NumberColumn(format="percent"),
    })

ui.sources(["digital", "population"])

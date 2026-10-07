import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, kouiki, maps, muni, ui
from lib.charts import man, updown

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}の全体像", "いくつかの市町村をひとつの観光圏として見ます。広域を選ぶか、市町村を自由に組めます。", kicker="広域連携")
k, mem = kouiki.picker("top")
LABEL = kouiki.label(k)
if len(mem) < 1:
    st.info("市町村を選んでください。")
    st.stop()

t = muni.vtable()
ly, Y, M = t.attrs["year"], t.attrs["Y"], t.attrs["M"]
mt = t.reindex(mem).dropna(subset=["visitors"])
km = kouiki.monthly(mem)
y = muni.yearly()
ky = y[[c for c in mem if c in y]].sum(axis=1)
ytd, ytd_ly = muni.ytd(Y, M)[mem].sum(), muni.ytd(Y - 1, M)[mem].sum()
share = ky[ly] / y.loc[ly].sum()
top = mt.sort_values("visitors", ascending=False)

ui.insight(
    f"{Y}年1〜{M}月に{LABEL}（{len(mem)}市町村）を観光で訪れた人は、市町村の合計で <b>{man(ytd)}</b>（前年の同じ時期より{updown(ytd / ytd_ly - 1)}）。"
    f"<br>{ly}年は {man(ky[ly])}"
    + (f"（前年より{updown(ky[ly] / ky[ly - 1] - 1)}）" if ly - 1 in ky.index else "")
    + f"で、県内市町村の合計の {share:.0%}。"
    + (f"<b>{top.name.iloc[0]}</b> が圏域の {top.visitors.iloc[0] / ky[ly]:.0%} を占めます。" if len(top) > 1 else "")
)

ui.group(f"{Y}年の状況", f"1〜{M}月の累計。前年の同じ時期と比べて")
cols = st.columns(4)
with cols[0]:
    ui.kpi(f"観光来訪者数（1〜{M}月）", man(ytd), f"{Y - 1}年1〜{M}月 {man(ytd_ly)}", ytd / ytd_ly - 1)
with cols[1]:
    cm, lm = km.get(pd.Timestamp(Y, M, 1)), km.get(pd.Timestamp(Y - 1, M, 1))
    ui.kpi(f"{M}月の観光来訪者数", man(cm), f"{Y - 1}年{M}月 {man(lm)}", cm / lm - 1 if lm else None)
with cols[2]:
    pref_ytd = t.ytd.sum() / muni.ytd(Y - 1, M).sum() - 1
    ui.kpi("県全体の伸び（1〜{}月）".format(M), updown(pref_ytd), "77市町村の合計")
with cols[3]:
    up = mt[mt.ytd_yoy > 0]
    ui.kpi("前年を上回った市町村", f"{len(up)}／{len(mt)}", "1〜{}月の累計で".format(M))

ui.group(f"{ly}年の実績", "1年間")
cols = st.columns(4)
with cols[0]:
    ui.kpi("観光来訪者数（年間）", man(ky[ly]), f"{ly - 1}年 {man(ky[ly - 1])}" if ly - 1 in ky.index else "",
           ky[ly] / ky[ly - 1] - 1 if ly - 1 in ky.index else None)
with cols[1]:
    ui.kpi("県内市町村の合計に占める割合", f"{share:.1%}", f"{len(mem)}市町村")
with cols[2]:
    pop = muni.population().reindex(mem).sum()
    ui.kpi("住民1人あたりの来訪者", f"{ky[ly] / pop:,.0f}人", f"県全体 {y.loc[ly].sum() / muni.population().sum():,.0f}人")
with cols[3]:
    kl = km[km.index.year == ly]
    ui.kpi("いちばん多い月", f"{kl.idxmax().month}月", f"1年の {kl.max() / kl.sum():.0%}")

with ui.card():
    ui.block("圏域の範囲と、市町村ごとの人数", f"{ly}年の観光来訪者数")
    c1, c2 = st.columns([3, 2])
    with c1:
        g = data.municipalities()
        st.plotly_chart(maps.municipality_map(g, highlight=set(mem), outlines=data.kouiki(), focus=g[g.code.isin(mem)], height=420,
                                              values=mt.visitors.to_dict(), value_label=f"{ly}年の観光来訪者数", fmt=man, missing="（圏域の外）"),
                        use_container_width=True, config={"displaylogo": False})
    with c2:
        b = top.iloc[::-1]
        fig = go.Figure(go.Bar(y=b.name, x=b.visitors / ky[ly], orientation="h", marker_color=charts.MAIN,
                               text=[f"{v / ky[ly]:.0%}（{man(v)}）" for v in b.visitors], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} 圏域の %{x:.1%}<extra></extra>"))
        charts.layout(fig, height=max(260, 34 * len(b) + 70), title={"text": "圏域の中の割合", "font": {"size": 14}})
        fig.update_xaxes(tickformat=".0%", range=[0, b.visitors.max() / ky[ly] * 1.6])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    top3 = top.visitors.iloc[:3].sum() / ky[ly]
    ui.readout([
        f"上位{min(3, len(top))}市町村（{'・'.join(top.name.iloc[:3])}）で圏域の {top3:.0%} を占めます。" if len(top) > 3 else "",
        f"前年からの伸びがいちばん大きいのは **{mt.loc[mt.yoy.idxmax(), 'name']}**（{mt.yoy.max():+.0%}）"
        + (f"、いちばん小さいのは **{mt.loc[mt.yoy.idxmin(), 'name']}**（{mt.yoy.min():+.0%}）です。" if len(mt) > 1 else "です。")
        if mt.yoy.notna().any() else "",
    ], source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成。{kouiki.SUM_NOTE}")

with ui.card():
    ui.block("今年の積み上げ", f"1月からの累計（圏域の市町村の合計）。{Y}年と前年")
    fig = go.Figure()
    for yy, color, w in [(Y - 1, charts.CONTEXT, 2), (Y, charts.MAIN, 3.5)]:
        s = km[km.index.year == yy].cumsum()
        fig.add_trace(go.Scatter(x=[f"{m}月" for m in s.index.month], y=s.values / 1e4, name=f"{yy}年", mode="lines+markers",
                                 line={"color": color, "width": w}, hovertemplate=f"{yy}年 1〜%{{x}} 累計 %{{y:,.1f}}万人<extra></extra>"))
    charts.layout(fig, height=300, hovermode="x unified")
    fig.update_yaxes(title="万人", rangemode="tozero")
    ui.chart(fig)
    ui.readout([
        f"{Y}年1〜{M}月は前年の同じ時期より {updown(ytd / ytd_ly - 1)}（県全体は {updown(pref_ytd)}）。",
        f"前年を上回っている市町村: {'・'.join(up.name) or 'なし'}。",
    ], source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成。{kouiki.SUM_NOTE}")

ui.group("テーマごとに詳しく見る", LABEL)
sp = data.riyousha_spots()
ry = int(sp.year.max())
ks = sp[(sp.municipality_code.isin(mem)) & (sp.year == ry)].sort_values("total", ascending=False)
wins = [
    ("k1", "01", "市町村の役割は？", "人が集まる場所と伸びている場所", f"最も多いのは <b>{top.name.iloc[0]}</b>（圏域の {top.visitors.iloc[0] / ky[ly]:.0%}）。", "views/kouiki/1_members.py"),
    ("k2", "02", "季節のかぶり・すき間", "市町村ごとのピークの月", f"圏域のピークは <b>{kl.idxmax().month}月</b>。", "views/kouiki/2_season.py"),
    ("k3", "03", "どの観光地？", "圏域の観光地ランキング", f"利用者が最も多い観光地は <b>{ks.spot.iloc[0]}</b>。" if len(ks) else "県の調査対象の観光地はありません。", "views/kouiki/3_spots.py"),
    ("k4", "04", "宿泊・気象", "県内5エリアの宿泊と雪", "宿泊と外国人の割合、冬の雪。", "views/kouiki/4_stay.py"),
    ("k5", "05", "他の広域と比べると？", "10広域・県平均と比べる", f"{ly}年の県内シェアは <b>{share:.0%}</b>。", "views/kouiki/5_compare.py"),
]
for i in range(0, len(wins), 3):
    cols = st.columns(3)
    for c, w in zip(cols, wins[i:i + 3]):
        with c:
            ui.window(*w)

ui.sources(["digital", "riyousha", "boundaries"])

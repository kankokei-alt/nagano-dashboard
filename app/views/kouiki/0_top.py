import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, data, kouiki, maps, muni, ui
from lib.charts import man, updown

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}の全体像", "いくつかの市町村をひとつの観光圏として見ます。広域を選ぶか、市町村を自由に組めます。", kicker="広域連携")
k, mem = kouiki.picker("top")
LABEL = kouiki.label(k)
if len(mem) < 1:
    st.info("市町村を選んでください。")
    st.stop()
muni.require_digital()

t = muni.vtable()
ly, Y, SPAN, LBL = t.attrs["year"], t.attrs["Y"], t.attrs["span"], t.attrs["label"]
v = muni.visitors()
mt = t.reindex(mem)
K = kouiki.stats(mem)
TEN = pd.DataFrame({kk: kouiki.stats(kouiki.members(kk)) for kk in kouiki.names()}).T  # 10広域
km = kouiki.monthly(mem)
pref_tot = t.visitors.sum()
top = mt.dropna(subset=["visitors"]).sort_values("visitors", ascending=False)
SRC = f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成。{kouiki.SUM_NOTE}"

ui.insight(
    f"{LBL}に{LABEL}（{len(mem)}市町村）を観光で訪れた人は、市町村の合計で <b>{man(K['now'])}</b>"
    + (f"（前年の同じ時期より{updown(K['now_yoy'])}）" if pd.notna(K["now_yoy"]) else "") + "。"
    + f"<br>{ly}年は <b>{man(K['visitors'])}</b> で、県内市町村の合計の {K['visitors'] / pref_tot:.0%}。"
    + (f"<b>{top.name.iloc[0]}</b> が圏域の {top.visitors.iloc[0] / K['visitors']:.0%} を占めます。" if len(top) > 1 else "")
)

ui.group(f"{Y}年の状況", f"{SPAN}（公表されている月）")
cols = st.columns(4)
last = pd.Timestamp(Y, t.attrs["months"][-1], 1)
with cols[0]:
    ui.kpi(f"観光来訪者数（{SPAN}）", man(K["now"]), f"県平均（10広域の平均） {man(TEN.now.mean())}",
           K["now_yoy"] if pd.notna(K["now_yoy"]) else None)
with cols[1]:
    ui.kpi(f"{last.month}月の観光来訪者数", man(km.get(last)), "圏域の市町村の合計")
with cols[2]:
    ui.kpi("県内市町村の合計に占める割合", f"{K['now'] / t.now.sum():.1%}", f"{SPAN}")
with cols[3]:
    big = mt.now.idxmax() if mt.now.notna().any() else None
    ui.kpi("いちばん多い市町村", mt.loc[big, "name"] if big else "—", f"圏域の {mt.now.max() / K['now']:.0%}" if big else "")
if not t.attrs["has_prev"]:
    st.caption(muni.NOTE_2025)

ui.group(f"{ly}年の実績", "1年間")
cols = st.columns(4)
with cols[0]:
    ui.kpi("観光来訪者数（年間）", man(K["visitors"]), f"県平均（10広域の平均） {man(TEN.visitors.mean())}",
           K["yoy"] if pd.notna(K["yoy"]) else None)
with cols[1]:
    ui.kpi("県内市町村の合計に占める割合", f"{K['visitors'] / pref_tot:.1%}", f"{len(mem)}市町村")
with cols[2]:
    pr = pref_tot / muni.population().reindex(t.index)[t.visitors.notna()].sum()
    ui.kpi("住民1人あたりの来訪者", f"{K['per_resident']:,.0f}人", f"県全体 {pr:,.0f}人")
with cols[3]:
    kl = km[km.index.year == ly]
    ui.kpi("いちばん多い月", f"{kl.idxmax().month}月", f"1年の {kl.max() / kl.sum():.0%}")

with ui.card():
    ui.block("圏域の範囲と、市町村ごとの人数", f"{ly}年の観光来訪者数")
    c1, c2 = st.columns([3, 2])
    with c1:
        g = data.municipalities()
        st.plotly_chart(maps.municipality_map(g, highlight=set(mem), outlines=data.kouiki(), focus=g[g.code.isin(mem)], height=420,
                                              values=top.visitors.to_dict(), value_label=f"{ly}年の観光来訪者数", fmt=man,
                                              missing="（圏域の外、または公表なし）"),
                        use_container_width=True, config={"displaylogo": False})
    with c2:
        b = top.iloc[::-1]
        fig = go.Figure(go.Bar(y=b.name, x=b.visitors / K["visitors"], orientation="h", marker_color=charts.MAIN,
                               text=[f"{x / K['visitors']:.0%}（{man(x)}）" for x in b.visitors], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} 圏域の %{x:.1%}<extra></extra>"))
        charts.layout(fig, height=max(260, 34 * len(b) + 70), title={"text": "圏域の中の割合", "font": {"size": 14}})
        fig.update_xaxes(tickformat=".0%", range=[0, b.visitors.max() / K["visitors"] * 1.6])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    miss = [muni.name(c) for c in mem if c not in top.index]
    ui.readout([
        f"上位{min(3, len(top))}市町村（{'・'.join(top.name.iloc[:3])}）で圏域の {top.visitors.iloc[:3].sum() / K['visitors']:.0%} を占めます。" if len(top) > 3 else "",
        f"住民1人あたりの来訪者がいちばん多いのは **{top.loc[top.per_resident.idxmax(), 'name']}**（{top.per_resident.max():,.0f}人）です。" if len(top) else "",
        f"{'・'.join(miss)}は、人数が少なく公表されていない月があるため、地図と割合に入れていません。" if miss else "",
    ], source=SRC)

with ui.card():
    ui.block("県平均と比べる", f"{ly}年。県平均は10広域の平均")
    sel = compare.Sel(me=k, me_name=LABEL, names={k: LABEL})
    c1, c2 = st.columns(2)
    with c1:
        ui.chart(compare.bars(sel, pd.Series({k: K["visitors"]}), TEN.visitors.mean(), fmt=man, title="観光来訪者数（年間）"))
    with c2:
        ui.chart(compare.bars(sel, pd.Series({k: K["per_resident"]}), pr, fmt=lambda x: f"{x:,.0f}人", title="住民1人あたりの来訪者",
                              pref_label="県全体"))
    ui.readout(compare.readout(sel, pd.Series({k: K["visitors"]}), TEN.visitors.mean(), "観光来訪者数", fmt=man)
               + compare.readout(sel, pd.Series({k: K["per_resident"]}), pr, "住民1人あたりの来訪者", fmt=lambda x: f"{x:,.0f}人",
                                 higher="多い", lower="少ない", pref_label="県全体"),
               source=SRC)

ui.group("テーマごとに詳しく見る", LABEL)
sp = data.riyousha_spots()
ry = int(sp.year.max())
ks = sp[(sp.municipality_code.isin(mem)) & (sp.year == ry)].sort_values("total", ascending=False)
wins = [
    ("k1", "01", "市町村の役割は？", "人が集まる場所と、住民1人あたり",
     f"最も多いのは <b>{top.name.iloc[0]}</b>（圏域の {top.visitors.iloc[0] / K['visitors']:.0%}）。" if len(top) else "市町村ごとの人数。",
     "views/kouiki/1_members.py"),
    ("k2", "02", "季節のかぶり・すき間", "市町村ごとのピークの月", f"圏域のピークは <b>{kl.idxmax().month}月</b>。", "views/kouiki/2_season.py"),
    ("k3", "03", "どの観光地？", "圏域の観光地ランキング",
     f"利用者が最も多い観光地は <b>{ks.spot.iloc[0]}</b>。" if len(ks) else "県の調査対象の観光地はありません。", "views/kouiki/3_spots.py"),
    ("k4", "04", "宿泊・気象", "県内5エリアの宿泊と雪", "宿泊と外国人の割合、冬の雪。", "views/kouiki/4_stay.py"),
    ("k5", "05", "他の広域と比べると？", "10広域・県平均と比べる", f"{ly}年の県内シェアは <b>{K['visitors'] / pref_tot:.0%}</b>。",
     "views/kouiki/5_compare.py"),
]
for i in range(0, len(wins), 3):
    cols = st.columns(3)
    for c, w in zip(cols, wins[i:i + 3]):
        with c:
            ui.window(*w)

ui.sources(["digital", "riyousha", "boundaries"])

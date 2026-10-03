import streamlit as st

from lib import data, maps, ui

ui.setup("広域で連携する", "複数の市町村をまとめて、ひとつの観光圏として見るページです。")

g = data.municipalities()
k = data.kouiki()
mode = st.radio("まとめ方", ["10広域から選ぶ", "市町村を自由に選ぶ"], horizontal=True)
if mode == "10広域から選ぶ":
    region = st.selectbox("広域", sorted(g.kouiki.unique()), index=sorted(g.kouiki.unique()).index("北アルプス"))
    selected = g[g.kouiki == region]
else:
    picks = st.multiselect("市町村（2つ以上）", g.sort_values("code").name.tolist(),
                           default=["白馬村", "小谷村", "大町市"])
    selected = g[g.name.isin(picks)]

if selected.empty:
    st.warning("市町村を選んでください。")
    st.stop()

ui.insight(
    f"選んだ {len(selected)} 市町村の合計面積は {selected.area_km2.sum():,.0f} km²"
    f"（県の {selected.area_km2.sum() / g.area_km2.sum():.0%}）です。"
    "統計を取り込むと、圏域内で「来訪が集中している所」と「周遊の余地がある所」をここに示します。"
)
st.plotly_chart(
    maps.municipality_map(g, highlight=set(selected.code), outlines=k, focus=selected, height=520),
    use_container_width=True,
)
st.caption(maps.ATTRIBUTION)

c1, c2 = st.columns(2)
with c1:
    st.subheader("圏域内のシェア")
    ui.pending("市町村ごとの利用者数の割合", ["riyousha"])
with c2:
    st.subheader("季節のかぶり・すき間")
    ui.pending("市町村ごとの月別ピークの比較", ["riyousha", "digital"])

ui.sources(["boundaries", "riyousha", "digital"])

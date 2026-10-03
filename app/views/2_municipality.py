import streamlit as st

from lib import data, maps, ui

ui.setup("市町村を深掘りする", "ひとつの市町村を選んで、エリアごとの特徴と季節の動きを見るページです。")

g = data.municipalities()
names = g.sort_values("code").name.tolist()
name = st.selectbox("市町村を選んでください", names, index=names.index("長野市"))
row = g[g.name == name].iloc[0]

ui.insight(f"{name}は{row.kouiki}広域（{row.chiiki}）に属し、面積は {row.area_km2:,.0f} km² です。"
           "観光地ごとの利用者数を取り込むと、伸びているエリア・落ちているエリアをここに要約します。")

left, right = st.columns([3, 2])
with left:
    st.plotly_chart(
        maps.municipality_map(g, highlight={row.code}, focus=g[g.code == row.code], height=480),
        use_container_width=True,
    )
    st.caption(maps.ATTRIBUTION)
with right:
    st.subheader("市町村内のエリア")
    areas = data.sub_areas()
    areas = areas[areas.municipality_code == row.code]
    if areas.empty:
        st.info("この市町村のエリア分けはまだ定義していません。観光地ごとの集計から作れます。")
    else:
        for a in areas.itertuples():
            st.markdown(f"- **{a.area_name}** … {a.definition}")
        st.caption("エリアの境界は、国勢調査の小地域（町丁・字）を組み合わせて正確に作る予定です。")

c1, c2 = st.columns(2)
with c1:
    st.subheader("観光地ランキング")
    ui.pending("観光地別の利用者数（前年比つき）", ["riyousha"])
with c2:
    st.subheader("季節ごとの来訪")
    ui.pending("季節別の利用者数・人流", ["riyousha", "digital"])

ui.sources(["boundaries", "riyousha", "digital", "kokusei_area"])

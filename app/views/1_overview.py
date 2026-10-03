import streamlit as st

from lib import data, maps, ui

ui.setup("長野県を俯瞰する", "県全体の観光の「いま」を、4つの数字と地図でつかむページです。")

ui.insight(
    "県全体の延べ宿泊者数・客室稼働率・外国人比率・観光消費額を、"
    "前年とコロナ前（2019年）と比べて表示します。（統計データの取り込み後に、自動で文章が入ります）"
)

cols = st.columns(4)
for col, (label, sub) in zip(
    cols,
    [("延べ宿泊者数（直近月）", "前年同月比"), ("客室稼働率（直近月）", "前年同月差"),
     ("外国人宿泊者の割合", "前年同月差"), ("観光消費額（年）", "前年比")],
):
    with col:
        ui.kpi(label, None, sub)

st.subheader("どこに人が来ているか")
g = data.municipalities()
st.plotly_chart(maps.municipality_map(g, outlines=data.kouiki()), use_container_width=True)
st.caption(f"太線は10広域の境界です。地図にマウスを乗せると市町村名が出ます。{maps.ATTRIBUTION}")

c1, c2 = st.columns(2)
with c1:
    st.subheader("季節ごとの波")
    ui.pending("月別の延べ宿泊者数（直近5年）", ["shukuhaku"])
with c2:
    st.subheader("どこから来ているか")
    ui.pending("県内・県外・海外の割合と、訪日客の国・地域", ["irikomi", "jnto"])

ui.sources(["boundaries", "shukuhaku", "irikomi", "riyousha", "jnto"])

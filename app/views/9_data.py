import streamlit as st

from lib import data, ui

ui.setup("データについて", "このダッシュボードが使っている公的統計の一覧と、取り込みの状況です。")

ds = data.datasets()
done = ds.status.str.startswith("取得済み").sum()
st.progress(done / len(ds), text=f"{len(ds)} 件中 {done} 件を取り込み済み")
st.dataframe(
    ds[["name", "provider", "granularity", "use", "status", "url"]],
    column_config={
        "name": "データ", "provider": "提供元", "granularity": "細かさ", "use": "使いみち",
        "status": "状況", "url": st.column_config.LinkColumn("出典", display_text="開く"),
    },
    hide_index=True, use_container_width=True,
)
st.subheader("主なイベント・制度（予測の手がかり）")
ev = data.events()
st.dataframe(ev, hide_index=True, use_container_width=True)

st.subheader("公表値との照合")
st.markdown("取り込んだ数字は、公表されている年の合計などと照合してから使っています。合わなかった年は使わずに、理由を残しています。")
for name, label in [("jnto", "訪日外客統計（JNTO）"), ("weather", "過去の気象データ（気象庁）")]:
    c = data.checks(name)
    bad = c[~c.adopted]
    st.markdown(f"**{label}** … {len(c)}件を照合し、{len(c) - len(bad)}件が一致" + ("。" if bad.empty else f"、{len(bad)}件は使っていません。"))
    if not bad.empty:
        cols = {"station": "地点", "year": "年", "item": "項目", "reason": "使わない理由"}
        st.dataframe(bad[[k for k in cols if k in bad.columns]].rename(columns=cols), hide_index=True, use_container_width=True)

c = data.checks("macro")
st.markdown("**消費者物価指数・景気ウォッチャー・消費者態度指数（e-Stat）**")
st.dataframe(c.rename(columns={"indicator": "指標", "months": "照合した月数", "mismatch": "合わなかった月数", "detail": "メモ"}),
             hide_index=True, use_container_width=True)

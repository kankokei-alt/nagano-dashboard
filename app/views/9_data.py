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

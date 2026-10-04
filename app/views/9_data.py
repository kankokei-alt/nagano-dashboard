import pandas as pd
import streamlit as st

from lib import data, ui

ui.setup("データと出典", "使っている公的統計の一覧と、整えたデータのダウンロード。", kicker="資料室")

# 整えたデータ（data/processed）: ファイル, 名前, 中身, 出典の id
FILES = [
    ("shukuhaku_monthly.parquet", "宿泊旅行統計（都道府県×月）", "延べ宿泊者数・日本人・外国人・客室稼働率（施設タイプ別）、2011年1月〜", "shukuhaku"),
    ("shukuhaku_residence.parquet", "宿泊旅行統計（長野県・居住地別）", "県内／県外別の延べ宿泊者数、月別", "shukuhaku"),
    ("shukuhaku_nationality.parquet", "宿泊旅行統計（長野県・国籍別）", "外国人延べ宿泊者数、国・地域×月", "shukuhaku"),
    ("shukuhaku_area.parquet", "宿泊旅行統計（県内5エリア）", "延べ宿泊者数・外国人、エリア×月（2021年〜）", "shukuhaku"),
    ("irikomi.parquet", "観光入込客統計（長野県）", "入込客数・消費額単価・観光消費額、目的×日帰り/宿泊×県内/県外×四半期", "irikomi"),
    ("riyousha_spots.parquet", "観光地利用者統計（観光地別の明細）", "観光地ごとの延利用者数・月別・消費額（2011年〜）", "riyousha"),
    ("riyousha_history.parquet", "観光地利用者統計（年次推移）", "観光地ごとの延利用者数、年別（2010年〜）", "riyousha"),
    ("jnto_monthly.parquet", "訪日外客統計（JNTO）", "全国の訪日外客数、国籍×月（2003年〜）", "jnto"),
    ("weather_monthly.parquet", "過去の気象データ（気象庁）", "主要6地点の平均気温・降雪量・最深積雪、月別", "weather"),
    ("macro_monthly.parquet", "物価・景気の指標（e-Stat）", "消費者物価指数・景気ウォッチャー・消費者態度指数、月別", "macro"),
    ("calendar_monthly.parquet", "祝日・連休カレンダー", "月ごとの休日数・3連休の回数", "holidays"),
]

ds = data.datasets().set_index("id")
done = ds.status.str.startswith("取得済み").sum()

with ui.card():
    ui.block("データのダウンロード", "このダッシュボードの数字の元になっている、整えたデータ（CSV）")
    for f, name, what, sid in FILES:
        path = data.PROCESSED / f
        if not path.exists():
            continue
        c1, c2, c3 = st.columns([3, 1.2, 1.2])
        with c1:
            st.markdown(f"**{name}**  \n<span style='color:#5f6b7a;font-size:.85rem'>{what}</span>", unsafe_allow_html=True)
        with c2:
            url = ds.loc[sid, "url"] if sid in ds.index else None
            if isinstance(url, str):
                st.link_button("公表ページ ↗", url, use_container_width=True)
        with c3:
            st.download_button("CSV", pd.read_parquet(path).to_csv(index=False).encode("utf-8-sig"),
                               file_name=f.replace(".parquet", ".csv"), mime="text/csv", use_container_width=True, key=f"dl_{f}")
    st.caption("文字コードは UTF-8（BOM 付き）で、Excel でそのまま開けます。各グラフの下の「数値を見る・ダウンロード」からも、"
               "そのグラフの数字だけを取り出せます。")

with ui.card():
    ui.block("使っている統計", f"{len(ds)} 件中 {done} 件を取り込み済み")
    st.dataframe(
        ds.reset_index()[["name", "provider", "granularity", "use", "status", "url"]],
        column_config={
            "name": "データ", "provider": "提供元", "granularity": "細かさ", "use": "使いみち",
            "status": "状況", "url": st.column_config.LinkColumn("公表ページ", display_text="開く ↗"),
        },
        hide_index=True, use_container_width=True,
    )

with ui.card():
    ui.block("公表値との照合", "取り込んだ数字は、公表されている合計などと照合してから使っています。合わなかったものは使わずに理由を残しています")
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

with ui.card():
    ui.block("主なイベント・制度", "予測の手がかりとして使っているもの（config/events.csv）")
    ev = data.events().copy()
    for c in ("start", "end"):
        ev[c] = ev[c].dt.strftime("%Y-%m-%d").fillna("")
    st.dataframe(ev.rename(columns={"start": "開始", "end": "終了", "name": "名前", "scope": "範囲", "kind": "種類", "note": "メモ"}),
                 hide_index=True, use_container_width=True)

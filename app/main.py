"""長野県 観光分析ダッシュボード（エントリポイント）。

起動: streamlit run app/main.py

構成: 長野県全体（扉ページ ＋ 詳細ページ）／市町村／広域連携／資料室（レポート作成・データと出典）
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="長野県 観光データ", page_icon=":material/landscape:", layout="wide")

PREF = [  # 長野県全体（扉ページから各詳細へ）
    ("views/pref/0_top.py", "長野県の全体像", ":material/home:"),
    ("views/pref/1_visitors.py", "誰が来ている？", ":material/groups:"),
    ("views/pref/2_inbound.py", "海外からのお客さま", ":material/public:"),
    ("views/pref/3_season.py", "いつ来ている？", ":material/calendar_month:"),
    ("views/pref/4_stay.py", "宿と稼働率", ":material/hotel:"),
    ("views/pref/5_spend.py", "いくら使っている？", ":material/payments:"),
    ("views/pref/6_areas.py", "県内のどこへ？", ":material/location_on:"),
    ("views/pref/7_compare.py", "他の県と比べる", ":material/leaderboard:"),
    ("views/pref/8_forecast.py", "これからの見通し（ベータ版）", ":material/trending_up:"),
]
pages = {
    "長野県全体": [st.Page(p, title=t, icon=i, default=(n == 0)) for n, (p, t, i) in enumerate(PREF)],
    "市町村": [st.Page(p, title=t, icon=i, url_path=u) for p, t, i, u in [
        ("views/muni/0_top.py", "市町村の全体像", ":material/location_city:", "muni"),
        ("views/muni/1_visitors.py", "誰が来ている？（市町村）", ":material/groups:", "muni_visitors"),
        ("views/muni/2_season.py", "いつ来ている？（市町村）", ":material/calendar_month:", "muni_season"),
        ("views/muni/3_spots.py", "観光地（市町村）", ":material/landscape:", "muni_spots"),
        ("views/muni/4_spend.py", "消費（市町村）", ":material/payments:", "muni_spend"),
        ("views/muni/5_area.py", "宿泊・気象（市町村）", ":material/map:", "muni_area"),
        ("views/muni/6_compare.py", "他の市町村と比べる", ":material/leaderboard:", "muni_compare"),
    ]],
    "広域連携": [st.Page(p, title=t, icon=i, url_path=u) for p, t, i, u in [
        ("views/kouiki/0_top.py", "広域の全体像", ":material/hub:", "kouiki"),
        ("views/kouiki/1_members.py", "市町村の役割（広域）", ":material/groups:", "kouiki_members"),
        ("views/kouiki/2_season.py", "季節（広域）", ":material/calendar_month:", "kouiki_season"),
        ("views/kouiki/3_spots.py", "観光地（広域）", ":material/landscape:", "kouiki_spots"),
        ("views/kouiki/4_stay.py", "宿泊・気象（広域）", ":material/hotel:", "kouiki_stay"),
        ("views/kouiki/5_compare.py", "他の広域と比べる", ":material/leaderboard:", "kouiki_compare"),
    ]],
    "資料室": [st.Page("views/report.py", title="レポートを作る", icon=":material/description:"),
               st.Page("views/9_data.py", title="データと出典", icon=":material/database:")],
}
from lib import ui  # noqa: E402

st.navigation(pages, position="hidden").run()  # メニューは lib.ui のサイトヘッダーで出す
ui.footer()

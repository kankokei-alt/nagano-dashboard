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
    "市町村": [st.Page("views/2_municipality.py", title="市町村を深掘りする", icon=":material/location_city:")],
    "広域連携": [st.Page("views/3_kouiki.py", title="広域で連携する", icon=":material/hub:")],
    "資料室": [st.Page("views/report.py", title="レポートを作る", icon=":material/description:"),
               st.Page("views/9_data.py", title="データと出典", icon=":material/database:")],
}
st.navigation(pages, position="top").run()

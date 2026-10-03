"""長野県 観光分析ダッシュボード（エントリポイント）。

起動: streamlit run app/main.py

構成: 長野県全体（扉ページ ＋ 詳細ページ）／市町村／広域連携／資料室
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="長野県 観光ダッシュボード", page_icon="🏔️", layout="wide")

PREF = [  # 長野県全体（扉ページから各詳細へ）
    ("views/pref/0_top.py", "長野県の全体像", "🗾"),
    ("views/pref/1_visitors.py", "誰が来ている？", "👥"),
    ("views/pref/2_inbound.py", "海外からのお客さま", "🌏"),
    ("views/pref/3_season.py", "いつ来ている？", "📅"),
    ("views/pref/4_stay.py", "宿と稼働率", "🛏️"),
    ("views/pref/5_spend.py", "いくら使っている？", "💴"),
    ("views/pref/6_areas.py", "県内のどこへ？", "📍"),
    ("views/pref/7_compare.py", "他の県と比べる", "🏔️"),
    ("views/pref/8_forecast.py", "これからの見通し（ベータ版）", "📈"),
]
pages = {
    "長野県全体": [st.Page(p, title=t, icon=i, default=(n == 0)) for n, (p, t, i) in enumerate(PREF)],
    "市町村": [st.Page("views/2_municipality.py", title="市町村を深掘りする", icon="🔍")],
    "広域連携": [st.Page("views/3_kouiki.py", title="広域で連携する", icon="🤝")],
    "資料室": [st.Page("views/9_data.py", title="データについて", icon="📚")],
}
st.navigation(pages, position="top").run()

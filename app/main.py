"""長野県 観光分析ダッシュボード（エントリポイント）。

起動: streamlit run app/main.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="長野県 観光ダッシュボード", page_icon="🏔️", layout="wide")

pages = [
    st.Page("views/1_overview.py", title="長野県を俯瞰する", icon="🗾", default=True),
    st.Page("views/2_municipality.py", title="市町村を深掘りする", icon="🔍"),
    st.Page("views/3_kouiki.py", title="広域で連携する", icon="🤝"),
    st.Page("views/4_forecast.py", title="稼働率予測（ベータ版）", icon="📈"),
    st.Page("views/9_data.py", title="データについて", icon="📚"),
]
st.navigation(pages, position="top").run()

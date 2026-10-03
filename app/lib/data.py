"""データ読み込み（キャッシュ付き）。ページからはここだけを使う。"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed"
CONFIG = ROOT / "config"


@st.cache_data
def municipalities() -> gpd.GeoDataFrame:
    return gpd.read_file(PROCESSED / "municipalities.geojson")


@st.cache_data
def kouiki() -> gpd.GeoDataFrame:
    """10広域（広域連合の範囲）で市町村を束ねたポリゴン。"""
    return gpd.read_file(PROCESSED / "kouiki.geojson")


@st.cache_data
def calendar_monthly() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "calendar_monthly.parquet")


@st.cache_data
def events() -> pd.DataFrame:
    return pd.read_csv(CONFIG / "events.csv", parse_dates=["start", "end"])


@st.cache_data
def datasets() -> pd.DataFrame:
    return pd.read_csv(CONFIG / "datasets.csv")


@st.cache_data
def sub_areas() -> pd.DataFrame:
    return pd.read_csv(CONFIG / "sub_areas.csv", dtype={"municipality_code": str})

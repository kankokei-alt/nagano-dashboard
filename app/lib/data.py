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


@st.cache_data
def shukuhaku(pref_code: str = "20") -> pd.DataFrame:
    """宿泊旅行統計（月次）を横持ちで返す。列: guests, japanese, foreign, occupancy（いずれも施設計）。"""
    d = pd.read_parquet(PROCESSED / "shukuhaku_monthly.parquet")
    d = d[(d.pref_code == pref_code) & (d.facility == "計")]
    w = d.pivot_table(index="ym", columns="metric", values="value")
    w["status"] = d.drop_duplicates("ym").set_index("ym").status
    return w.sort_index()


@st.cache_data
def irikomi() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "irikomi.parquet")


@st.cache_data
def riyousha_spots() -> pd.DataFrame:
    """観光地ごとの明細（最新年と前年）。人数は人、消費額は円。"""
    return pd.read_parquet(PROCESSED / "riyousha_spots.parquet")


@st.cache_data
def riyousha_history() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "riyousha_history.parquet")

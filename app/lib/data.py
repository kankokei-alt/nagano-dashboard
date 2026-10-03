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


@st.cache_data
def shukuhaku_residence() -> pd.DataFrame:
    """長野県の延べ宿泊者数の県内/県外（月次, 2010年〜）。"""
    return pd.read_parquet(PROCESSED / "shukuhaku_residence.parquet")


@st.cache_data
def shukuhaku_nationality() -> pd.DataFrame:
    """長野県の国籍（出身地）別 外国人延べ宿泊者数（月次, 従業者10人以上の施設）。"""
    return pd.read_parquet(PROCESSED / "shukuhaku_nationality.parquet")


@st.cache_data
def shukuhaku_area() -> pd.DataFrame:
    """長野県内5エリア（観光庁の広域市町村130区分）別の延べ宿泊者数（月次, 2021年〜）。"""
    return pd.read_parquet(PROCESSED / "shukuhaku_area.parquet")


@st.cache_data
def shukuhaku_area_map() -> pd.DataFrame:
    return pd.read_csv(CONFIG / "shukuhaku_areas.csv", dtype={"municipality_code": str})


@st.cache_data
def jnto() -> pd.DataFrame:
    """JNTO 訪日外客数（国籍×月, 2003年〜）。kind: total/region/country/sub、status: 確定/暫定/推計。"""
    return pd.read_parquet(PROCESSED / "jnto_monthly.parquet")


@st.cache_data
def weather() -> pd.DataFrame:
    """気象庁 主要地点の月別の平均気温・降雪量・最深積雪。"""
    return pd.read_parquet(PROCESSED / "weather_monthly.parquet")


@st.cache_data
def checks(name: str) -> pd.DataFrame:
    """取り込み時の公表値との照合結果（data/processed/checks/）。"""
    return pd.read_csv(PROCESSED / "checks" / f"{name}.csv")


MODELS = ROOT / "models"


@st.cache_data
def forecast() -> pd.DataFrame:
    return pd.read_parquet(MODELS / "forecast.parquet")


@st.cache_data
def backtest() -> pd.DataFrame:
    return pd.read_parquet(MODELS / "backtest.parquet")


@st.cache_data
def forecast_meta() -> dict:
    import json
    return json.loads((MODELS / "forecast_meta.json").read_text(encoding="utf-8"))


@st.cache_data
def shukuhaku_occupancy(pref_code: str = "20") -> pd.DataFrame:
    """客室稼働率（%）を施設タイプ別の横持ちで返す。"""
    d = pd.read_parquet(PROCESSED / "shukuhaku_monthly.parquet")
    d = d[(d.pref_code == pref_code) & (d.metric == "occupancy")]
    return d.pivot_table(index="ym", columns="facility", values="value").sort_index()

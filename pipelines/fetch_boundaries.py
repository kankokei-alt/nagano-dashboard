"""長野県77市町村の行政区域ポリゴンを取得し、表示用に整形する。

出典: 国土数値情報 行政区域データ（N03, 2020年1月1日時点, 国土交通省）
取得元: niiyz/JapanCityGeoJson（N03 を市町村単位の GeoJSON に変換したもの）
  - 国交省サイト (nlftp.mlit.go.jp) に直接届く環境では N03 の原本を使うのが望ましい。

出力:
  data/processed/municipalities.geojson  … 表示用（約30mで簡素化、属性付き）
  data/processed/kouiki.geojson          … 10広域で束ねたポリゴン
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import shapely

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/boundaries"
OUT = ROOT / "data/processed/municipalities.geojson"
SRC = "https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/geojson/20/{code}.json"
SIMPLIFY_DEG = 0.0003  # 約30m。市町村単位の表示には十分で、ファイルを軽くする


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    master = pd.read_csv(ROOT / "config/municipalities.csv", dtype=str)
    frames = []
    for code in master.code:
        path = RAW / f"{code}.json"
        if not path.exists():
            r = requests.get(SRC.format(code=code), timeout=60)
            r.raise_for_status()
            path.write_bytes(r.content)
        g = gpd.read_file(path)
        frames.append(g.dissolve().assign(code=code)[["code", "geometry"]])

    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    gdf = gdf.merge(master, on="code")
    # 面積は平面直角座標系 第VIII系（長野県）で計算
    gdf["area_km2"] = (gdf.to_crs("EPSG:6676").area / 1e6).round(2)
    gdf["geometry"] = shapely.make_valid(gdf.geometry.values)
    # 隣り合う市町村の境界線を共有したまま簡素化する（すき間や重なりを作らない）
    gdf["geometry"] = shapely.coverage_simplify(gdf.geometry.values, SIMPLIFY_DEG)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT, driver="GeoJSON")
    print(f"wrote {OUT} ({len(gdf)} municipalities, total {gdf.area_km2.sum():,.0f} km2)")

    kouiki = gdf.dissolve(by="kouiki", as_index=False, aggfunc={"area_km2": "sum", "chiiki": "first"})
    kouiki.to_file(OUT.with_name("kouiki.geojson"), driver="GeoJSON")
    print(f"wrote kouiki.geojson ({len(kouiki)} regions)")


if __name__ == "__main__":
    main()

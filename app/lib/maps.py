"""地図描画。境界は国土数値情報 N03 の正確なポリゴンを使う。

外部の地図タイルや地図データ（CDN）を一切読み込まない描画にしている。
庁内ネットワークなどで外部サイトに出られなくても、境界と色分けは必ず表示される。
経度方向は緯度に応じて縮めて（scaleratio）、見た目の形が歪まないようにしている。
"""
import math

import geopandas as gpd
import plotly.graph_objects as go

NEUTRAL = "#d9d8d3"
HIGHLIGHT = "#2a78d6"
LINE = "#ffffff"
OUTLINE = "#52514e"
ATTRIBUTION = "境界: 国土数値情報（行政区域データ, 国土交通省）を加工"


def _rings(geom, exterior_only: bool = False):
    """Polygon/MultiPolygon の輪郭を (lons, lats) の並びで返す。None でリングを区切る。"""
    lons, lats = [], []
    for poly in getattr(geom, "geoms", [geom]):
        rings = [poly.exterior] if exterior_only else [poly.exterior, *poly.interiors]
        for ring in rings:
            x, y = ring.xy
            lons += list(x) + [None]
            lats += list(y) + [None]
    return lons, lats


def municipality_map(
    g: gpd.GeoDataFrame,
    highlight: set[str] | None = None,
    outlines: gpd.GeoDataFrame | None = None,
    focus: gpd.GeoDataFrame | None = None,
    height: int = 560,
) -> go.Figure:
    """市町村を塗り分ける地図。highlight に入れた市町村コードだけ色を付ける。"""
    highlight = highlight or set()
    fig = go.Figure()
    for r in g.itertuples():
        lons, lats = _rings(r.geometry, exterior_only=True)
        fig.add_trace(
            go.Scatter(
                x=lons, y=lats, mode="lines", fill="toself", hoveron="fills",
                fillcolor=HIGHLIGHT if r.code in highlight else NEUTRAL,
                line={"color": LINE, "width": 0.8},
                name=r.name, showlegend=False,
                text=f"<b>{r.name}</b><br>{r.kouiki}広域・{r.chiiki}<br>面積 {r.area_km2:,.1f} km²",
                hoverinfo="text",
            )
        )
    if outlines is not None:
        lons, lats = [], []
        for geom in outlines.geometry:
            x, y = _rings(geom)
            lons += x
            lats += y
        fig.add_trace(go.Scatter(x=lons, y=lats, mode="lines", line={"color": OUTLINE, "width": 2},
                                 hoverinfo="skip", showlegend=False))

    minx, miny, maxx, maxy = (focus if focus is not None else g).total_bounds
    pad = max(maxx - minx, maxy - miny) * 0.05
    axis = {"visible": False, "showgrid": False, "zeroline": False}
    fig.update_xaxes(range=[minx - pad, maxx + pad], **axis)
    fig.update_yaxes(range=[miny - pad, maxy + pad], scaleanchor="x",
                     scaleratio=1 / math.cos(math.radians((miny + maxy) / 2)), **axis)
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0}, height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        dragmode="pan", hoverlabel={"bgcolor": "white"},
    )
    return fig

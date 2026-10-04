"""地図描画。境界は国土数値情報 N03 の正確なポリゴンを使う。

外部の地図タイルや地図データ（CDN）を一切読み込まない描画にしている。
庁内ネットワークなどで外部サイトに出られなくても、境界と色分けは必ず表示される。
経度方向は緯度に応じて縮めて（scaleratio）、見た目の形が歪まないようにしている。
"""
import math

import geopandas as gpd
import numpy as np
import plotly.graph_objects as go

NEUTRAL = "#d9d8d3"
HIGHLIGHT = "#2f6db5"
LINE = "#ffffff"
OUTLINE = "#52514e"
SEQ = ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # 青の濃淡（少→多）
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


def _bins(vals: list[float], k: int = 5) -> list[float]:
    """件数がほぼ同じになる区切り（分位点）。きりのよい数に丸める。"""
    q = np.quantile(vals, np.linspace(0, 1, k + 1))
    def nice(x):
        if x <= 0:
            return 0
        e = 10 ** max(int(math.log10(x)) - 1, 0)
        return round(x / e) * e
    edges = sorted({nice(x) for x in q[1:-1]})
    return [min(vals), *edges, max(vals)]


def municipality_map(
    g: gpd.GeoDataFrame,
    highlight: set[str] | None = None,
    outlines: gpd.GeoDataFrame | None = None,
    focus: gpd.GeoDataFrame | None = None,
    height: int = 560,
    values: dict[str, float] | None = None,
    value_label: str = "",
    fmt=lambda v: f"{v:,.0f}",
) -> go.Figure:
    """市町村を塗り分ける地図。

    highlight に入れた市町村コードだけ色を付ける。values（市町村コード→数値）を渡すと、
    数値の大きさで青の濃淡に塗り分ける（データのない市町村は灰色のまま）。
    """
    highlight = highlight or set()
    bins = _bins(list(values.values())) if values else []
    fig = go.Figure()
    for r in g.itertuples():
        lons, lats = _rings(r.geometry, exterior_only=True)
        text = f"<b>{r.name}</b><br>{r.kouiki}広域・{r.chiiki}"
        if values is not None:
            v = values.get(r.code)
            fill = NEUTRAL if v is None else SEQ[sum(v >= b for b in bins[1:-1])]
            text += f"<br>{value_label} {fmt(v) if v is not None else '調査対象の観光地なし'}"
        else:
            fill = HIGHLIGHT if r.code in highlight else NEUTRAL
            text += f"<br>面積 {r.area_km2:,.1f} km²"
        fig.add_trace(
            go.Scatter(
                x=lons, y=lats, mode="lines", fill="toself", hoveron="fills",
                fillcolor=fill, line={"color": LINE, "width": 0.8},
                name=r.name, showlegend=False, text=text, hoverinfo="text",
            )
        )
    for i in range(len(bins) - 1):  # 凡例（色の区切り）
        label = f"{fmt(bins[i])}〜" if i == len(bins) - 2 else f"{fmt(bins[i])}〜{fmt(bins[i + 1])}"
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=label,
                                 marker={"symbol": "square", "size": 14, "color": SEQ[i]}))
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
        legend={"orientation": "h", "yanchor": "top", "y": 0.0, "x": 0, "bgcolor": "rgba(0,0,0,0)"},
    )
    return fig

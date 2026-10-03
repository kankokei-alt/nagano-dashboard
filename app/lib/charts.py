"""グラフの共通設定。色は役割で決め、ページごとにばらばらにしない。"""
import plotly.graph_objects as go

MAIN = "#2a78d6"      # いま見てほしい系列（1番目の色）
SECOND = "#eb6834"    # 2番目の系列
THIRD = "#1baf7a"     # 3番目の系列
CONTEXT = "#a8a69f"   # 比べるための背景の系列（前年・コロナ前など）
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]  # 量の濃淡（青1色）
MONTHS = [f"m{i:02d}" for i in range(1, 13)]  # 観光地利用者統計の月別の列


def layout(fig: go.Figure, height: int = 340, **kw) -> go.Figure:
    fig.update_layout(
        height=height, margin={"l": 10, "r": 10, "t": 30, "b": 10},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        hoverlabel={"namelength": -1}, separators=".,", **kw,
    )
    fig.update_xaxes(showgrid=False, linecolor="rgba(128,128,128,.4)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,.18)", zeroline=False)
    return fig


def man(x: float, unit: str = "人") -> str:
    """人数を「178万人」のように読みやすくする。"""
    if x >= 1e8:
        return f"{x / 1e8:,.2f}億{unit}"
    if x >= 1e4:
        return f"{x / 1e4:,.0f}万{unit}" if x >= 1e5 else f"{x / 1e4:,.1f}万{unit}"
    return f"{x:,.0f}{unit}"


def yen(x: float) -> str:
    """金額を「1兆866億円」「3,644億円」のようにする。"""
    oku = round(x / 1e8)
    if oku >= 10000:
        return f"{oku // 10000}兆{oku % 10000:,}億円" if oku % 10000 else f"{oku // 10000}兆円"
    if oku >= 1:
        return f"{oku:,}億円"
    return f"{x / 1e4:,.0f}万円"


def pct(x: float, signed: bool = True) -> str:
    return f"{x:+.1%}" if signed else f"{x:.1%}"


def updown(x: float) -> str:
    """増減を言葉で。±0.5% 未満は「ほぼ同じ」。"""
    if abs(x) < 0.005:
        return "ほぼ同じ"
    return f"{abs(x):.0%}増" if x > 0 else f"{abs(x):.0%}減"

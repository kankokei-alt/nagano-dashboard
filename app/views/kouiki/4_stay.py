import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, kouiki, muni, ui
from lib.charts import man, updown

k = kouiki.current()
ui.setup(f"{kouiki.label(k)}の宿泊・気象", "観光庁の宿泊統計（県内5エリア）と、圏域の気象観測所の気温・雪。", kicker="広域連携")
k, mem = kouiki.picker("stay")
LABEL = kouiki.label(k)
m = muni.master()

# ---- 宿泊 ----
amap = data.shukuhaku_area_map()
hit = amap[amap.municipality_code.isin(mem)].area.value_counts()
if not hit.empty:
    with ui.card():
        ui.block("宿泊の動き", "観光庁の宿泊統計の県内5エリア別（圏域の市町村を含むエリア）。延べ宿泊者数と外国人")
        area = hit.index[0]
        if len(hit) > 1:
            area = st.radio("エリア", list(hit.index), horizontal=True, key="kstay_area",
                            format_func=lambda a: amap[amap.area == a].area_full.iloc[0].removeprefix("長野県"))
        members = amap[amap.area == area]
        sa = data.shukuhaku_area()
        sa = sa[sa.area == area]
        n = sa.groupby(sa.ym.dt.year).size()
        yr = sa.groupby(sa.ym.dt.year)[["guests", "foreign"]].sum()[n == 12]
        full = int(yr.index.max())
        c1, c2 = st.columns([3, 2])
        with c1:
            fig = go.Figure()
            for col, label, color in [("jp", "日本人", charts.MAIN), ("foreign", "外国人", charts.SECOND)]:
                vv = yr.guests - yr.foreign if col == "jp" else yr.foreign
                fig.add_trace(go.Bar(x=yr.index, y=vv / 1e4, name=label, marker_color=color, marker_line={"color": "white", "width": 1},
                                     hovertemplate=f"%{{x}}年 {label} %{{y:,.0f}}万人泊<extra></extra>"))
            charts.layout(fig, height=300, barmode="stack", bargap=0.3, legend_traceorder="normal")
            fig.update_yaxes(title="延べ宿泊者数（万人泊）")
            fig.update_xaxes(dtick=1)
            ui.chart(fig)
        with c2:
            mm = sa[sa.ym.dt.year == full].set_index(sa[sa.ym.dt.year == full].ym.dt.month)
            fig = go.Figure(go.Bar(x=[f"{i}月" for i in mm.index], y=mm.foreign / mm.guests, marker_color=charts.SECOND,
                                   hovertemplate="%{x} 外国人の割合 %{y:.1%}<extra></extra>"))
            charts.layout(fig, height=300, title={"text": f"外国人の割合（{full}年・月別）", "font": {"size": 14}})
            fig.update_yaxes(tickformat=".0%")
            ui.chart(fig)
        out = sorted(set(members.municipality_code) - set(mem))
        ui.readout([
            f"{members.area_full.iloc[0].removeprefix('長野県')}エリアの {full}年の延べ宿泊者数は {man(yr.guests[full], '人泊')}"
            + (f"（前年より{updown(yr.guests[full] / yr.guests[full - 1] - 1)}）" if full - 1 in yr.index else "")
            + f"、外国人の割合は {yr.foreign[full] / yr.guests[full]:.0%} です。",
            f"外国人がいちばん多い月は {mm.foreign.idxmax()}月、日本人を含めた全体では {mm.guests.idxmax()}月です。",
            f"このエリアには圏域の外の市町村（{len(out)}）も入ります。市町村ごとの宿泊者数は公表されていません。" if out else "",
        ], source="観光庁「宿泊旅行統計調査」広域市町村（130区分）別参考表")

# ---- 気象 ----
stn = pd.read_csv(data.CONFIG / "weather_stations.csv", dtype={"municipality_code": str})
ks = stn[stn.municipality_code.isin(mem)]
if ks.empty:
    ks = stn[stn.kouiki.isin(m.loc[mem, "kouiki"].unique())]
if len(ks):
    wx = data.weather()
    wx = wx[wx.station.isin(ks.station)].assign(season=lambda d: d.ym.dt.year + (d.ym.dt.month >= 8))
    with ui.card():
        ui.block("冬ごとの最深積雪", "圏域の気象観測所。冬（12〜3月）の最も深い積雪")
        last = int(wx[wx.ym.dt.month == 3].ym.dt.year.max())
        s = wx[(wx.season <= last) & (wx.season >= wx.ym.dt.year.min() + 1)].groupby(["season", "station"]).snow_depth_max.max().unstack()
        s = s.dropna(how="all")
        fig = go.Figure()
        pal = [charts.MAIN, charts.SECOND, charts.THIRD, charts.CONTEXT]
        for i, col in enumerate(s.columns):
            if s[col].fillna(0).max() <= 0:
                continue
            fig.add_trace(go.Bar(x=[f"{y - 1}〜{y % 100:02d}" for y in s.index], y=s[col], name=col, marker_color=pal[i % 4],
                                 hovertemplate=f"{col} %{{x}}年の冬 %{{y:.0f}}cm<extra></extra>"))
        charts.layout(fig, height=320, barmode="group")
        fig.update_xaxes(type="category", tickangle=-45)
        fig.update_yaxes(title="cm")
        ui.chart(fig)
        pts = []
        for col in s.columns:
            c = s[col].dropna()
            if len(c) > 1 and c.max() > 0:
                pts.append(f"{col}: 最も新しい冬は {c.iloc[-1]:.0f}cm（それまでの平均 {c.iloc[:-1].mean():.0f}cm の {c.iloc[-1] / c.iloc[:-1].mean():.0%}）。")
        ui.readout(pts or ["この観測所では積雪を観測していません。"], source="気象庁「過去の気象データ」")

ui.sources(["shukuhaku", "weather"])

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, data, muni, ui
from lib.charts import man, updown

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}の宿泊・気象", "宿泊（県内5エリア）の動きと、近くの気象観測所の気温と雪。", kicker="市町村")
code = muni.picker("area")
cmp = muni.compare_picker(code, "area")
m = muni.master().loc[code]

ui.insight(
    f"{NAME}は{m.chiiki}地域・{m.kouiki}広域に属し、観光庁の宿泊統計では <b>{m.area5}</b>エリアに入ります。"
    if isinstance(m.area5, str) else f"{NAME}は{m.chiiki}地域・{m.kouiki}広域に属します。"
)

# ---- 2. 宿泊（5エリア） ----
if isinstance(m.area5, str):
    with ui.card():
        ui.block(f"宿泊の動き（{m.area5}エリア）", "観光庁の宿泊統計の県内5エリア別。延べ宿泊者数と外国人の割合（月別）")
        ar = data.shukuhaku_area()
        ar["area"] = ar.area.str.replace("長野県", "")
        mine_a = ar[ar.area == m.area5].set_index("ym").sort_index()
        mine_a["share"] = mine_a.foreign / mine_a.guests
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure(go.Bar(x=mine_a.index, y=mine_a.guests / 1e4, marker_color=charts.MAIN,
                                   hovertemplate="%{x|%Y年%-m月} %{y:,.1f}万人泊<extra></extra>"))
            charts.layout(fig, height=300, bargap=0.15, title={"text": "延べ宿泊者数（万人泊）", "font": {"size": 14}})
            fig.update_xaxes(tickformat="%Y年", dtick="M12")
            ui.chart(fig)
        with c2:
            fig = go.Figure(go.Scatter(x=mine_a.index, y=mine_a.share, mode="lines+markers", line={"color": charts.SECOND, "width": 2.5},
                                       hovertemplate="%{x|%Y年%-m月} 外国人の割合 %{y:.1%}<extra></extra>"))
            charts.layout(fig, height=300, title={"text": "宿泊者に占める外国人の割合", "font": {"size": 14}})
            fig.update_yaxes(tickformat=".0%", rangemode="tozero")
            fig.update_xaxes(tickformat="%Y年", dtick="M12")
            ui.chart(fig)
        yy = mine_a.groupby(mine_a.index.year)[["guests", "foreign"]].sum()
        full = yy[mine_a.groupby(mine_a.index.year).size() == 12]
        ly = full.index.max()
        members = data.shukuhaku_area_map()
        members = members[members.area.str.replace("長野県", "") == m.area5].municipality
        ui.readout([
            f"{ly}年の{m.area5}エリアの延べ宿泊者数は {man(full.loc[ly, 'guests'], '人泊')}"
            + (f"（前年より{updown(full.loc[ly, 'guests'] / full.loc[ly - 1, 'guests'] - 1)}）" if ly - 1 in full.index else "")
            + f"、外国人の割合は {full.loc[ly, 'foreign'] / full.loc[ly, 'guests']:.0%} です。",
            f"外国人の割合がいちばん高い月は {mine_a.share.idxmax():%Y年%-m月}（{mine_a.share.max():.0%}）でした。",
            f"このエリアには {len(members)} 市町村が入ります（{'・'.join(members.head(12))}{'など' if len(members) > 12 else ''}）。市町村ごとの宿泊者数は公表されていません。",
        ], source="観光庁「宿泊旅行統計調査」広域市町村（130区分）別参考表")

# ---- 3. 気象 ----
stn = pd.read_csv(data.CONFIG / "weather_stations.csv", dtype={"municipality_code": str})
here = stn[stn.municipality_code == code]
st_row = here.iloc[0] if len(here) else (stn[stn.kouiki == m.kouiki].iloc[0] if (stn.kouiki == m.kouiki).any() else None)
if st_row is not None:
    wx = data.weather()
    w = wx[wx.station == st_row.station].set_index("ym").sort_index()
    with ui.card():
        same = "市内の" if st_row.municipality_code == code else f"同じ{m.kouiki}広域の"
        ui.block(f"気温と雪（{st_row.station}）", f"{same}気象観測所。月別の平均気温と、冬ごとの最深積雪")
        c1, c2 = st.columns(2)
        with c1:
            t = w.temp_mean.dropna()
            ly = t.index.max().year
            fig = go.Figure()
            normal = t[t.index.year < ly].groupby(t[t.index.year < ly].index.month).mean()
            fig.add_trace(go.Scatter(x=[f"{i}月" for i in normal.index], y=normal.values, name=f"平年（{t.index.min().year}〜{ly - 1}年平均）",
                                     mode="lines", line={"color": charts.CONTEXT, "width": 2, "dash": "dot"},
                                     hovertemplate="平年 %{x} %{y:.1f}℃<extra></extra>"))
            cy = t[t.index.year == ly]
            fig.add_trace(go.Scatter(x=[f"{i}月" for i in cy.index.month], y=cy.values, name=f"{ly}年", mode="lines+markers",
                                     line={"color": charts.SECOND, "width": 3}, hovertemplate=f"{ly}年 %{{x}} %{{y:.1f}}℃<extra></extra>"))
            charts.layout(fig, height=300, hovermode="x unified", title={"text": "月平均気温（℃）", "font": {"size": 14}})
            ui.chart(fig)
        snow = w.snow_depth_max.dropna()
        with c2:
            if len(snow) and snow.max() > 0:
                s = w.assign(season=w.index.year + (w.index.month >= 8)).groupby("season").snow_depth_max.max()
                first = w.index.min()
                s = s[[y for y in s.index if pd.Timestamp(y - 1, 12, 1) >= first and pd.Timestamp(y, 3, 1) <= w.index.max()]].dropna()
                fig = go.Figure(go.Bar(x=[f"{y - 1}〜{y % 100:02d}" for y in s.index], y=s.values, marker_color=charts.MAIN,
                                       hovertemplate="%{x}年の冬 最深積雪 %{y:.0f}cm<extra></extra>"))
                charts.layout(fig, height=300, title={"text": "冬ごとの最深積雪（cm）", "font": {"size": 14}})
                fig.update_xaxes(type="category", tickangle=-45)
                ui.chart(fig)
            else:
                st.markdown("この観測所では積雪を観測していません。")
        pts = []
        d = (cy - normal.reindex(cy.index.month).values)
        if len(d):
            pts.append(f"{ly}年はこれまでの月で、平年より平均 {d.mean():+.1f}℃。いちばん差が大きいのは {d.abs().idxmax().month}月（{d[d.abs().idxmax()]:+.1f}℃）です。")
        if len(snow) and snow.max() > 0 and len(s) > 1:
            pts.append(f"最も新しい冬（{s.index[-1] - 1}〜{s.index[-1] % 100:02d}年）の最深積雪は {s.iloc[-1]:.0f}cm で、それまでの平均（{s.iloc[:-1].mean():.0f}cm）の {s.iloc[-1] / s.iloc[:-1].mean():.0%} でした。")
        ui.readout(pts, source="気象庁「過去の気象データ」。年ごとの値が資料不足の冬は表示していません")


# ---- 比べる ----
def station_of(c):
    mm = muni.master().loc[c]
    h = stn[stn.municipality_code == c]
    if len(h):
        return h.iloc[0].station
    k = stn[stn.kouiki == mm.kouiki]
    return k.iloc[0].station if len(k) else None


wx = data.weather()
wx = wx.assign(season=wx.ym.dt.year + (wx.ym.dt.month >= 8))
last = int(wx[wx.ym.dt.month == 3].ym.dt.year.max())  # 3月まで観測がそろった最新の冬
win = wx[wx.season == last].groupby("station").snow_depth_max.max()
avg = wx[(wx.season < last)].groupby(["station", "season"]).snow_depth_max.max().groupby(level=0).mean()
codes = [c for c in cmp.all if station_of(c) is not None]
if codes:
    with ui.card():
        ui.block("比べる：冬の雪", f"{last - 1}〜{last % 100:02d}年の冬の最深積雪（最寄りの気象観測所）")
        vals = pd.Series({c: win.get(station_of(c)) for c in codes})
        sub = cmp.__class__(me=cmp.me, me_name=cmp.me_name, codes=[c for c in cmp.codes if c in codes],
                            names={c: f"{cmp.label(c)}（{station_of(c)}）" for c in codes}, pref=False)
        ui.chart(compare.bars(sub, vals, fmt=lambda x: f"{x:.0f}cm"))
        compare.hint(cmp)
        ui.readout([
            "それぞれの平年（観測開始〜前の冬の平均）との比: "
            + "、".join(f"{sub.label(c)} {vals[c] / avg[station_of(c)]:.0%}" for c in codes
                       if pd.notna(vals[c]) and avg.get(station_of(c), 0) > 0) + "。",
            "同じ観測所を使う市町村は同じ値です（観測所は各広域に1つ以上）。",
        ], source="気象庁「過去の気象データ」")

ui.sources(["shukuhaku", "weather"])

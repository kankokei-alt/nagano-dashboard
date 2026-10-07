import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, data, muni, ui
from lib.charts import man, updown

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}の全体像", "観光で訪れた人の数と、その動き。下のテーマから詳しく見られます。", kicker="市町村")
code = muni.picker("top")
cmp = muni.compare_picker(code, "top")

muni.require_digital()
v = muni.visitors()
if code not in v:
    st.info(f"{NAME}は、デジタル観光統計オープンデータに観光来訪者数がありません。")
    st.stop()
t = muni.vtable()
ly, Y, M = t.attrs["year"], t.attrs["Y"], t.attrs["M"]
me = t.loc[code]
mv = v[code]
y = muni.yearly()
pop = muni.population().get(code)

ui.insight(
    f"{Y}年1〜{M}月に{NAME}を観光で訪れた人は <b>{man(me.ytd)}</b>（前年の同じ時期より{updown(me.ytd_yoy)}）。"
    f"<br>{ly}年の1年間では <b>{man(me.visitors)}</b>"
    + (f"（前年より{updown(me.yoy)}）" if pd.notna(me.yoy) else "")
    + f"で、県内77市町村で <b>{muni.rank(t, 'visitors', code)}</b> です。"
)

# ---- 今年 ----
ui.group(f"{Y}年の状況", f"1〜{M}月の累計。前年の同じ時期と比べて")
cols = st.columns(4)
with cols[0]:
    ui.kpi(f"観光来訪者数（1〜{M}月）", man(me.ytd), f"{Y - 1}年1〜{M}月 {man(muni.ytd(Y - 1, M)[code])}", me.ytd_yoy)
with cols[1]:
    cur_m, ly_m = mv.get(pd.Timestamp(Y, M, 1)), mv.get(pd.Timestamp(Y - 1, M, 1))
    ui.kpi(f"{M}月の観光来訪者数", man(cur_m), f"{Y - 1}年{M}月 {man(ly_m)}" if pd.notna(ly_m) else "",
           cur_m / ly_m - 1 if pd.notna(ly_m) and ly_m else None)
with cols[2]:
    ui.kpi(f"伸び（1〜{M}月）の県内順位", muni.rank(t, "ytd_yoy", code), f"県全体 {updown(t.ytd.sum() / muni.ytd(Y - 1, M).sum() - 1)}")
with cols[3]:
    ui.kpi(f"県内の順位（1〜{M}月の人数）", muni.rank(t, "ytd", code), f"県内市町村の合計の {me.ytd / t.ytd.sum():.1%}")

with ui.card():
    ui.block("今年の積み上げ", f"1月からの累計。{Y}年と前年")
    fig = go.Figure()
    for yy, color, w in [(Y - 1, charts.CONTEXT, 2), (Y, charts.MAIN, 3.5)]:
        s = mv[mv.index.year == yy].cumsum()
        fig.add_trace(go.Scatter(x=[f"{m}月" for m in s.index.month], y=s.values / 1e4, name=f"{yy}年", mode="lines+markers",
                                 line={"color": color, "width": w}, hovertemplate=f"{yy}年 1〜%{{x}} 累計 %{{y:,.1f}}万人<extra></extra>"))
    charts.layout(fig, height=320, hovermode="x unified")
    fig.update_yaxes(title="万人", rangemode="tozero")
    ui.chart(fig)
    mm = mv[mv.index.year == Y] / mv[mv.index.year == Y - 1].reindex(mv[mv.index.year == Y].index - pd.DateOffset(years=1)).values - 1
    up = [f"{d.month}月" for d, r in mm.items() if r > 0]
    ui.readout([
        f"{Y}年1〜{M}月の累計は {man(me.ytd)}で、前年の同じ時期より {updown(me.ytd_yoy)}。",
        f"前年の同じ月を上回ったのは {'・'.join(up)} です。" if up and len(up) < len(mm) else
        ("どの月も前年を上回っています。" if up else "どの月も前年を下回っています。"),
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

# ---- 昨年 ----
ui.group(f"{ly}年の実績", "1年間の観光来訪者数")
cols = st.columns(4)
with cols[0]:
    ui.kpi("観光来訪者数（年間）", man(me.visitors), f"{ly - 1}年 {man(y.loc[ly - 1, code])}" if ly - 1 in y.index else "", me.yoy)
with cols[1]:
    ui.kpi("県内の順位", muni.rank(t, "visitors", code), f"県内市町村の合計の {me.share:.1%}")
with cols[2]:
    ui.kpi("住民1人あたりの来訪者", f"{me.per_resident:,.0f}人" if pd.notna(me.per_resident) else "—",
           f"人口 {pop:,.0f}人（2020年国勢調査）" if pop else "")
with cols[3]:
    mon_ly = mv[mv.index.year == ly]
    ui.kpi("いちばん多い月", f"{mon_ly.idxmax().month}月", f"1年の {mon_ly.max() / mon_ly.sum():.0%}")

with ui.card():
    ui.block("年ごとの観光来訪者数", f"{int(y.index.min())}年から。12か月そろった年")
    fig = go.Figure(go.Bar(x=y.index, y=y[code] / 1e4, marker_color=charts.MAIN, text=[man(x) for x in y[code]],
                           textposition="outside", cliponaxis=False, hovertemplate="%{x}年 %{y:,.1f}万人<extra></extra>"))
    charts.layout(fig, height=300, bargap=0.35)
    fig.update_yaxes(title="万人", range=[0, y[code].max() / 1e4 * 1.2])
    fig.update_xaxes(dtick=1)
    ui.chart(fig)
    first = int(y.index.min())
    ui.readout([
        f"{first}年から{ly}年で {y.loc[ly, code] / y.loc[first, code]:.2f} 倍になりました（県内市町村の合計は {y.loc[ly].sum() / y.loc[first].sum():.2f} 倍）。",
        f"いちばん多かったのは {y[code].idxmax()}年（{man(y[code].max())}）です。",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成。2021年はコロナの影響を受けています")

# ---- 比べる ----
with ui.card():
    ui.block("比べる：月ごとの観光来訪者数", "選んだ市町村と県平均（77市町村の平均）。左右で伸びの比較もできます")
    mode = st.segmented_control("表し方", ["人数", f"前年同月比"], default="人数", key="top_cmp_mode")
    recent = v[v.index >= pd.Timestamp(Y - 2, 1, 1)]
    if mode == "人数":
        df = recent[[c for c in cmp.all if c in recent]] / 1e4
        fig = compare.lines(cmp, df, pref=recent.mean(axis=1) / 1e4, y_title="万人", hover="%{y:,.1f}万人")
    else:
        yoy = (v / v.shift(12) - 1)
        yoy = yoy[yoy.index >= pd.Timestamp(Y - 1, 1, 1)]
        pref_yoy = (v.sum(axis=1) / v.sum(axis=1).shift(12) - 1).reindex(yoy.index)
        fig = compare.lines(cmp, yoy[[c for c in cmp.all if c in yoy]], pref=pref_yoy, hover="%{y:+.0%}", pref_label="県全体")
        fig.update_yaxes(tickformat="+.0%")
        fig.add_hline(y=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
    fig.update_xaxes(tickformat="%Y年%-m月")
    ui.chart(fig)
    compare.hint(cmp)
    ui.readout(compare.readout(cmp, t.ytd_yoy, t.ytd.sum() / muni.ytd(Y - 1, M).sum() - 1, f"{Y}年1〜{M}月の伸び",
                               fmt=charts.signed, higher="大きい", lower="小さい", pref_label="県全体")
               + compare.readout(cmp, t.ytd, t.ytd.mean(), f"1〜{M}月の人数", fmt=man, higher="多い", lower="少ない"),
               source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成。県平均は77市町村の平均")

# ---- 窓 ----
ui.group("テーマごとに詳しく見る", f"{NAME}について")
a = muni.annual()
sp_me = a[a.municipality_code == code].set_index("year")
sp = data.riyousha_spots()
ry = int(sp.year.max())
spots = sp[(sp.municipality_code == code) & (sp.year == ry)].sort_values("total", ascending=False)
m = muni.master().loc[code]
pk = mon_ly.idxmax().month
wins = [
    ("m1", "01", "誰が来ている？", "県内・県外、日帰り・宿泊",
     (f"調査対象の観光地では <b>{sp_me.loc[ry, 'kengai'] / (sp_me.loc[ry, 'kennai'] + sp_me.loc[ry, 'kengai']):.0%}</b> が県外から。"
      if ry in sp_me.index and sp_me.loc[ry, "kennai"] + sp_me.loc[ry, "kengai"] > 0 else "県内・県外の割合を見ます。"), "views/muni/1_visitors.py"),
    ("m2", "02", "いつ来ている？", "月ごとの波と、その変化", f"いちばん多いのは <b>{pk}月</b>（{ly}年の {mon_ly.max() / mon_ly.sum():.0%}）。", "views/muni/2_season.py"),
    ("m3", "03", "どの観光地？", "観光地ランキングと推移",
     f"利用者が最も多い観光地は <b>{spots.spot.iloc[0]}</b>。" if len(spots) else "県の調査対象の観光地はありません。", "views/muni/3_spots.py"),
    ("m4", "04", "いくら使っている？", "観光地での1人あたり消費額",
     (f"1人あたり <b>{sp_me.loc[ry, 'spend'] / sp_me.loc[ry, 'total']:,.0f}円</b>（調査対象の観光地）。"
      if ry in sp_me.index and sp_me.loc[ry, "spend"] > 0 else "観光地での消費額を見ます。"), "views/muni/4_spend.py"),
    ("m5", "05", "宿泊・気象", "宿泊（県内5エリア）と雪", f"宿泊統計では <b>{m.area5}</b>エリア。" if isinstance(m.area5, str) else "宿泊と気象。", "views/muni/5_area.py"),
    ("m6", "06", "他の市町村と比べると？", "県内での位置", f"{ly}年の伸びは県内 <b>{muni.rank(t, 'yoy', code)}</b>。", "views/muni/6_compare.py"),
]
for i in range(0, len(wins), 3):
    cols = st.columns(3)
    for c, w in zip(cols, wins[i:i + 3]):
        with c:
            ui.window(*w)

ui.sources(["digital", "riyousha", "population"])

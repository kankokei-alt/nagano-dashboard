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
t = muni.vtable()
ly, Y, LBL, SPAN = t.attrs["year"], t.attrs["Y"], t.attrs["label"], t.attrs["span"]
months = t.attrs["months"]
me = t.loc[code]
mv = v[code] if code in v else pd.Series(float("nan"), index=v.index)  # 公表されていない市町村は空の列
avg = v.mean(axis=1)  # 県平均（数字のある市町村の平均）
pop = muni.population().get(code)
SRC = "日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成"

if mv.dropna().empty:
    ui.insight(f"{NAME}は、デジタル観光統計で観光来訪者数が公表されていません（観光地点を訪れる人が少ない市町村は公表されません）。"
               "下のテーマから、県の観光地利用者統計や宿泊・気象の情報を見られます。")
else:
    if pd.notna(me.now):
        ui.insight(
            f"{LBL}に{NAME}を観光で訪れた人は <b>{man(me.now)}</b>"
            + (f"（前年の同じ時期より{updown(me.now_yoy)}）" if pd.notna(me.now_yoy) else "")
            + f"で、県内77市町村で <b>{muni.rank(t, 'now', code)}</b>。"
            + (f"<br>{ly}年の1年間では <b>{man(me.visitors)}</b>（県内 {muni.rank(t, 'visitors', code)}）、住民1人あたり {me.per_resident:,.0f}人です。"
               if pd.notna(me.visitors) else "")
        )
    else:
        ui.insight(f"{NAME}は、{LBL}に人数が公表されていない月があります（人数が少ない月は公表されません）。")

    # ---- 今年 ----
    ui.group(f"{Y}年の状況", f"{SPAN}（公表されている月）")
    cols = st.columns(4)
    last = pd.Timestamp(Y, months[-1], 1)
    with cols[0]:
        ui.kpi(f"観光来訪者数（{SPAN}）", man(me.now) if pd.notna(me.now) else "—", f"県平均 {man(t.now.mean())}",
               me.now_yoy if pd.notna(me.now_yoy) else None)
    with cols[1]:
        cm = mv.get(last)
        ui.kpi(f"{months[-1]}月の観光来訪者数", man(cm) if pd.notna(cm) else "—", f"県平均 {man(avg.get(last))}")
    with cols[2]:
        ui.kpi(f"県内の順位（{SPAN}）", muni.rank(t, "now", code), "人数の多い順")
    with cols[3]:
        ui.kpi("県内市町村の合計に占める割合", f"{me.now / t.now.sum():.1%}" if pd.notna(me.now) else "—", f"{SPAN}の合計")
    if not t.attrs["has_prev"]:
        st.caption(muni.NOTE_2025)

    with ui.card():
        ui.block("今年の月ごとの観光来訪者数", f"{LBL}。点線は県平均（数字のある市町村の平均）")
        cur = mv[mv.index.year == Y]
        fig = go.Figure(go.Bar(x=[f"{d.month}月" for d in cur.index], y=cur.values / 1e4, name=NAME, marker_color=charts.MAIN,
                               text=[man(x) if pd.notna(x) else "" for x in cur], textposition="outside", cliponaxis=False,
                               hovertemplate=f"{NAME} %{{x}} %{{y:,.1f}}万人<extra></extra>"))
        if t.attrs["has_prev"]:
            prev = mv.reindex([d - pd.DateOffset(years=1) for d in cur.index])
            fig.add_trace(go.Bar(x=[f"{d.month}月" for d in cur.index], y=prev.values / 1e4, name=f"{Y - 1}年", marker_color=charts.CONTEXT,
                                 hovertemplate=f"{Y - 1}年 %{{x}} %{{y:,.1f}}万人<extra></extra>"))
        a = avg[avg.index.year == Y]
        fig.add_trace(go.Scatter(x=[f"{d.month}月" for d in a.index], y=a.values / 1e4, name="県平均", mode="lines+markers",
                                 line={"color": compare.PREF_COLOR, "dash": "dot", "width": 2},
                                 hovertemplate="県平均 %{x} %{y:,.1f}万人<extra></extra>"))
        charts.layout(fig, height=320, barmode="group", bargap=0.3)
        fig.update_yaxes(title="万人", range=[0, max(cur.max(), a.max()) / 1e4 * 1.2])
        ui.chart(fig)
        r = (cur / a.reindex(cur.index)).dropna()
        ui.readout([
            f"{SPAN}でいちばん多いのは **{cur.idxmax().month}月**（{man(cur.max())}）、少ないのは {cur.idxmin().month}月（{man(cur.min())}）です。"
            if cur.notna().any() else "",
            (f"どの月も県平均の {r.min():.1f}〜{r.max():.1f} 倍です。" if r.min() >= 1 else
             f"どの月も県平均を下回っています（県平均の {charts.times(r.min())}〜{charts.times(r.max())}）。" if r.max() < 1 else
             f"県平均を上回った月: {'・'.join(f'{d.month}月' for d in r[r >= 1].index)}。") if len(r) else "",
        ], source=SRC)

    # ---- 1年間 ----
    ui.group(f"{ly}年の実績", "1年間の観光来訪者数")
    cols = st.columns(4)
    yv = mv[mv.index.year == ly]
    with cols[0]:
        ui.kpi("観光来訪者数（年間）", man(me.visitors) if pd.notna(me.visitors) else "—",
               f"県平均 {man(t.visitors.mean())}", me.yoy if pd.notna(me.yoy) else None)
    with cols[1]:
        ui.kpi("県内の順位", muni.rank(t, "visitors", code), f"県内市町村の合計の {me.share:.1%}" if pd.notna(me.share) else "")
    with cols[2]:
        ui.kpi("住民1人あたりの来訪者", f"{me.per_resident:,.0f}人" if pd.notna(me.per_resident) else "—",
               f"人口 {pop:,.0f}人（2020年国勢調査）" if pop else "")
    with cols[3]:
        ui.kpi("いちばん多い月", f"{yv.idxmax().month}月" if yv.notna().any() else "—",
               f"1年の {yv.max() / yv.sum():.0%}" if yv.notna().any() else "")

    with ui.card():
        ui.block("県平均と比べる", f"{ly}年。人数と、住民1人あたりの来訪者")
        pr = t.visitors.sum() / muni.population().reindex(t.index)[t.visitors.notna()].sum()
        c1, c2 = st.columns(2)
        with c1:
            ui.chart(compare.bars(cmp, t.visitors, t.visitors.mean(), fmt=man, title="観光来訪者数（年間）"))
        with c2:
            ui.chart(compare.bars(cmp, t.per_resident, pr, fmt=lambda x: f"{x:,.0f}人", title="住民1人あたりの来訪者",
                                  pref_label="県全体"))
        ui.readout(compare.readout(cmp, t.visitors, t.visitors.mean(), "観光来訪者数", fmt=man)
                   + compare.readout(cmp, t.per_resident, pr, "住民1人あたりの来訪者", fmt=lambda x: f"{x:,.0f}人",
                                     higher="多い", lower="少ない", pref_label="県全体"),
                   source=f"{SRC}、総務省「国勢調査」（2020年）。県平均は数字が公表されている市町村の平均")

    with ui.card():
        full = muni.yearly()
        if len(full) >= 2:
            ui.block("年ごとの観光来訪者数", "12か月そろった年")
            fig = go.Figure(go.Bar(x=full.index, y=full[code] / 1e4, marker_color=charts.MAIN, text=[man(x) for x in full[code]],
                                   textposition="outside", cliponaxis=False, hovertemplate="%{x}年 %{y:,.1f}万人<extra></extra>"))
            charts.layout(fig, height=300, bargap=0.35)
            fig.update_xaxes(dtick=1)
            ui.chart(fig)
            ui.readout([f"いちばん多かったのは {full[code].idxmax()}年（{man(full[code].max())}）です。"], source=SRC)
        else:
            ui.block("月ごとの観光来訪者数", f"{ly}年。点線は県平均")
            a = avg[avg.index.year == ly]
            fig = go.Figure(go.Bar(x=[f"{d.month}月" for d in yv.index], y=yv.values / 1e4, name=NAME, marker_color=charts.MAIN,
                                   hovertemplate=f"{NAME} %{{x}} %{{y:,.1f}}万人<extra></extra>"))
            fig.add_trace(go.Scatter(x=[f"{d.month}月" for d in a.index], y=a.values / 1e4, name="県平均", mode="lines+markers",
                                     line={"color": compare.PREF_COLOR, "dash": "dot", "width": 2},
                                     hovertemplate="県平均 %{x} %{y:,.1f}万人<extra></extra>"))
            charts.layout(fig, height=300, bargap=0.3)
            fig.update_yaxes(title="万人", rangemode="tozero")
            ui.chart(fig)
            ui.readout([
                f"{ly}年にいちばん多かったのは **{yv.idxmax().month}月**（{man(yv.max())}）、少なかったのは {yv.idxmin().month}月（{man(yv.min())}）です。"
                if yv.notna().any() else "",
                "季節ごとの詳しい動きは「季節」タブで見られます。",
            ], source=SRC)

# ---- 窓 ----
ui.group("テーマごとに詳しく見る", f"{NAME}について")
a = muni.annual()
sp_me = a[a.municipality_code == code].set_index("year")
sp = data.riyousha_spots()
ry = int(sp.year.max())
spots = sp[(sp.municipality_code == code) & (sp.year == ry)].sort_values("total", ascending=False)
m = muni.master().loc[code]
yv = mv[mv.index.year == ly]
has_sp = ry in sp_me.index and sp_me.loc[ry, "kennai"] + sp_me.loc[ry, "kengai"] > 0
wins = [
    ("m1", "01", "誰が来ている？", "県内・県外、日帰り・宿泊",
     f"調査対象の観光地では <b>{sp_me.loc[ry, 'kengai'] / (sp_me.loc[ry, 'kennai'] + sp_me.loc[ry, 'kengai']):.0%}</b> が県外から。"
     if has_sp else "県内・県外の割合を見ます。", "views/muni/1_visitors.py"),
    ("m2", "02", "いつ来ている？", "月ごとの波",
     f"いちばん多いのは <b>{yv.idxmax().month}月</b>（{ly}年の {yv.max() / yv.sum():.0%}）。" if yv.notna().any() else "月ごとの波を見ます。",
     "views/muni/2_season.py"),
    ("m3", "03", "どの観光地？", "観光地ランキングと推移",
     f"利用者が最も多い観光地は <b>{spots.spot.iloc[0]}</b>。" if len(spots) else "県の調査対象の観光地はありません。", "views/muni/3_spots.py"),
    ("m4", "04", "いくら使っている？", "観光地での1人あたり消費額",
     f"1人あたり <b>{sp_me.loc[ry, 'spend'] / sp_me.loc[ry, 'total']:,.0f}円</b>（調査対象の観光地）。"
     if ry in sp_me.index and sp_me.loc[ry, "spend"] > 0 else "観光地での消費額を見ます。", "views/muni/4_spend.py"),
    ("m5", "05", "宿泊・気象", "宿泊（県内5エリア）と雪", f"宿泊統計では <b>{m.area5}</b>エリア。" if isinstance(m.area5, str) else "宿泊と気象。",
     "views/muni/5_area.py"),
    ("m6", "06", "他の市町村と比べると？", "県内での位置", f"観光来訪者数は県内 <b>{muni.rank(t, 'visitors', code)}</b>（{ly}年）。",
     "views/muni/6_compare.py"),
]
for i in range(0, len(wins), 3):
    cols = st.columns(3)
    for c, w in zip(cols, wins[i:i + 3]):
        with c:
            ui.window(*w)

ui.sources(["digital", "riyousha", "population"])

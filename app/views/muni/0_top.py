import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, maps, muni, ui
from lib.charts import man, updown, yen

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}の全体像", "観光地にどれだけ人が訪れ、いくら使われているか。下のテーマから詳しく見られます。", kicker="市町村")
code = muni.picker("top")

a = muni.annual()
mine = a[a.municipality_code == code].set_index("year")
if mine.empty:
    st.info(f"{NAME}には、長野県「観光地利用者統計調査」の調査対象の観光地がありません。"
            "宿泊統計の5エリアや気象の情報は「エリア・宿泊・気象」タブで見られます。")
    st.page_link("views/muni/5_area.py", label="エリア・宿泊・気象を見る →")
    st.stop()

ry = int(mine.index.max())
cur, prv = mine.loc[ry], mine.loc[ry - 1] if ry - 1 in mine.index else None
t = muni.table(ry)
pop = muni.population().get(code)
sp = data.riyousha_spots()
spots = sp[(sp.municipality_code == code) & (sp.year == ry)].sort_values("total", ascending=False)
mon = cur[charts.MONTHS]
pref_tot = t.total.sum()

ui.insight(
    f"{ry}年に{NAME}の観光地（{int(cur.spots)}か所）を訪れた人は延べ <b>{man(cur.total)}</b>"
    + (f"（前年より{updown(cur.total / prv.total - 1)}" if prv is not None else "（")
    + (f"、2019年より{updown(cur.total / mine.loc[2019, 'total'] - 1)}）" if 2019 in mine.index else "）")
    + f"。県内77市町村で <b>{muni.rank(t, 'total', code)}</b>、県全体の {cur.total / pref_tot:.1%} を占めます。"
    + f"<br>いちばん人が多い観光地は <b>{spots.spot.iloc[0]}</b>"
    + (f"、いちばん多い月は <b>{int(mon.idxmax()[1:])}月</b>" if mon.notna().all() and mon.sum() > 0 else "")
    + f"、観光地での消費額は <b>{yen(cur.spend)}</b> です。"
)

ui.group(f"{ry}年の実績", "観光地利用者統計（調査対象の観光地の合計・延べ人数）")
cols = st.columns(4)
with cols[0]:
    ui.kpi("観光地の延べ利用者数", man(cur.total), f"{ry - 1}年 {man(prv.total)}" if prv is not None else "",
           cur.total / prv.total - 1 if prv is not None else None)
with cols[1]:
    ui.kpi("観光地での消費額", yen(cur.spend), f"{ry - 1}年 {yen(prv.spend)}" if prv is not None else "",
           cur.spend / prv.spend - 1 if prv is not None and prv.spend else None)
with cols[2]:
    ui.kpi("県内の順位（延べ利用者数）", muni.rank(t, "total", code), f"県全体の {cur.total / pref_tot:.1%}")
with cols[3]:
    ui.kpi("住民1人あたりの利用者", f"{cur.total / pop:,.0f}人" if pop else "—",
           f"人口 {pop:,.0f}人（2020年国勢調査）" if pop else "")

# ---- 推移 ----
with ui.card():
    ui.block("延べ利用者数の推移", "年ごと。大きな出来事の年に印")
    ev = data.events()
    m = muni.master().loc[code]
    mine_ev = ev[(ev.kind == "event") & ev.scope.map(lambda x: x in NAME or NAME in x or x == m.kouiki)]
    fig = go.Figure(go.Bar(x=mine.index, y=mine.total / 1e4, marker_color=charts.MAIN, name="延べ利用者数",
                           customdata=mine.spots, hovertemplate="%{x}年 %{y:,.1f}万人（観光地 %{customdata}か所）<extra></extra>"))
    for _, e in mine_ev.iterrows():
        if e.start.year in mine.index:
            fig.add_annotation(x=e.start.year, y=mine.loc[e.start.year, "total"] / 1e4, text=e["name"][:8], showarrow=True,
                               arrowhead=0, ay=-28, font={"size": 11})
    charts.layout(fig, height=330, bargap=0.25)
    fig.update_yaxes(title="万人")
    fig.update_xaxes(dtick=1)
    ui.chart(fig)
    best = mine.total.idxmax()
    first = int(mine.index.min())
    sp_changed = mine.spots.nunique() > 1
    ui.readout([
        f"{first}年から{ry}年までで最も多かったのは **{best}年**（{man(mine.total[best])}）です。",
        f"{ry}年は {first}年の {cur.total / mine.loc[first, 'total']:.2f} 倍、2019年の {cur.total / mine.loc[2019, 'total']:.2f} 倍です。" if 2019 in mine.index else "",
        f"調査対象の観光地の数が年によって {int(mine.spots.min())}〜{int(mine.spots.max())}か所と変わっているため、増減にはその影響も含まれます。" if sp_changed else "",
        ("この市町村に関わる大きな出来事: " + "、".join(f"{e.start.year}年 {e['name']}" for _, e in mine_ev.iterrows()) + "。") if len(mine_ev) else "",
    ], source="長野県「観光地利用者統計調査」")

# ---- 位置 ----
with ui.card():
    ui.block("どこにある？", f"{m.chiiki}地域・{m.kouiki}広域")
    c1, c2 = st.columns([3, 2])
    with c1:
        g = data.municipalities()
        st.plotly_chart(maps.municipality_map(g, highlight={code}, outlines=data.kouiki(), height=380),
                        use_container_width=True, config={"displaylogo": False})
    with c2:
        same = t[t.kouiki == m.kouiki].sort_values("total", ascending=False)
        st.markdown(f"**{m.kouiki}広域の市町村**（{ry}年の延べ利用者数）")
        for c, r in same.iterrows():
            mark = "**" if c == code else ""
            st.markdown(f"- {mark}{r['name']}{mark} … {man(r.total)}")
    ui.readout([
        f"{NAME}は{m.kouiki}広域の {len(same)} 市町村の中で {list(same.index).index(code) + 1}番目に人が多く、広域全体の {cur.total / same.total.sum():.0%} を占めます。" if code in same.index else "",
    ], source=f"国土数値情報（行政区域）。{maps.ATTRIBUTION}")

# ---- 窓 ----
ui.group("テーマごとに詳しく見る", f"{NAME}について")
kg = cur.kengai / (cur.kennai + cur.kengai)
sh = cur.shukuhaku / (cur.higaeri + cur.shukuhaku)
grow = (spots.set_index("spot").total / sp[(sp.municipality_code == code) & (sp.year == ry - 1)].set_index("spot").total - 1).dropna()
wins = [
    ("m1", "01", "誰が来ている？", "県内・県外、日帰り・宿泊", f"訪れた人の <b>{kg:.0%}</b> が県外から、<b>{sh:.0%}</b> が宿泊です。", "views/muni/1_visitors.py"),
    ("m2", "02", "いつ来ている？", "月ごとの波と、その変化",
     (f"いちばん多いのは <b>{int(mon.idxmax()[1:])}月</b>（1年の {mon.max() / mon.sum():.0%}）。" if mon.notna().all() and mon.sum() > 0 else "月別の内訳がない年です。"), "views/muni/2_season.py"),
    ("m3", "03", "どの観光地？", "観光地ランキングと推移",
     f"最多は <b>{spots.spot.iloc[0]}</b>（{man(spots.total.iloc[0])}）。" + (f"伸びが大きいのは {grow.idxmax()}。" if len(grow) > 1 else ""), "views/muni/3_spots.py"),
    ("m4", "04", "いくら使っている？", "観光地での消費額と単価", f"1人あたり <b>{cur.spend / cur.total:,.0f}円</b>（県内 {muni.rank(t, 'per_visit', code)}）。", "views/muni/4_spend.py"),
    ("m5", "05", "エリア・宿泊・気象", "市町村内のエリア、宿泊、雪", f"宿泊統計では <b>{m.area5}</b>エリアに入ります。" if isinstance(m.area5, str) else "市町村内のエリアと気象。", "views/muni/5_area.py"),
    ("m6", "06", "他の市町村と比べると？", "県内での位置", f"2019年比の伸びは県内 <b>{muni.rank(t, 'vs2019', code)}</b>。", "views/muni/6_compare.py"),
]
for i in range(0, len(wins), 3):
    cols = st.columns(3)
    for c, w in zip(cols, wins[i:i + 3]):
        with c:
            ui.window(*w)

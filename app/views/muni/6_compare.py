import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, data, muni, ui
from lib.charts import man

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}を他の市町村と比べる", "県内の順位、県平均との比較、同じ広域・似た規模の市町村。", kicker="市町村")
code = muni.picker("compare")
cmp = muni.compare_picker(code, "compare")
muni.require_digital()

t = muni.vtable()
A = dict(t.attrs)  # join すると attrs が消えるので先に取っておく
ly, Y, SPAN = A["year"], A["Y"], A["span"]
sp_ry = int(data.riyousha_spots().year.max())
s = muni.table(sp_ry)  # 観光地利用者統計（調査対象の観光地での割合）
t = t.join(s[["kengai", "shuku", "per_visit"]])
me = t.loc[code]
m = muni.master().loc[code]
pa = muni.annual()
pref_s = pa[pa.year == sp_ry][["kennai", "kengai", "higaeri", "shukuhaku", "spend", "total"]].sum()
pop = muni.population()
SRC = "日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成"

# (列, 名前, 書式, 県平均の値, 県平均の呼び方)。前年比は出せるときだけ
METRICS = [
    ("visitors", f"観光来訪者数（{ly}年）", man, t.visitors.mean(), "県平均"),
    ("now", f"観光来訪者数（{Y}年{SPAN}）", man, t.now.mean(), "県平均"),
    ("per_resident", "住民1人あたりの来訪者", lambda v: f"{v:,.0f}人", t.visitors.sum() / pop.reindex(t.index)[t.visitors.notna()].sum(), "県全体"),
]
if A["has_yoy"]:
    METRICS.append(("yoy", f"前年比（{ly}年）", lambda v: charts.signed(v, 1), t.visitors.sum() / (t.visitors / (1 + t.yoy)).sum() - 1, "県全体"))
if A["has_prev"]:
    METRICS.append(("now_yoy", f"前年比（{Y}年{SPAN}）", lambda v: charts.signed(v, 1), t.now.sum() / (t.now / (1 + t.now_yoy)).sum() - 1, "県全体"))
METRICS += [
    ("kengai", "県外の人の割合※", lambda v: f"{v:.0%}", pref_s.kengai / (pref_s.kennai + pref_s.kengai), "県全体"),
    ("shuku", "泊まりの人の割合※", lambda v: f"{v:.0%}", pref_s.shukuhaku / (pref_s.higaeri + pref_s.shukuhaku), "県全体"),
    ("per_visit", "1人あたり消費額※", lambda v: f"{v:,.0f}円", pref_s.spend / pref_s.total, "県全体"),
]

if pd.isna(me.visitors) and pd.isna(me.now):
    ui.insight(f"{NAME}は、デジタル観光統計で観光来訪者数が公表されていない月があるため、人数の順位はつけていません。"
               "下の ※ の項目（県の観光地利用者統計）は比べられます。")
else:
    ui.insight(
        f"{ly}年の{NAME}の観光来訪者数は県内 <b>{muni.rank(t, 'visitors', code)}</b>、住民1人あたりの来訪者は "
        f"<b>{muni.rank(t, 'per_resident', code)}</b>。{Y}年{SPAN}の人数は {muni.rank(t, 'now', code)} です。"
    )

# ---- 1. 順位 ----
with ui.card():
    ui.block("県内での順位", "77市町村の中で。大きいほうから数えた順位")
    for i in range(0, len(METRICS), 4):
        cols = st.columns(4)
        for c, (k, label, f, pv, pl) in zip(cols, METRICS[i:i + 4]):
            with c:
                val = me[k]
                ui.kpi(label, f(val) if pd.notna(val) else "—", f"県内 {muni.rank(t, k, code)}／{pl} {f(pv)}" if pd.notna(pv) else "")
    ui.readout([
        "※ は県の観光地利用者統計調査の、調査対象の観光地での値です（調査対象の観光地がない市町村は順位がつきません）。",
        "" if A["has_yoy"] else muni.NOTE_2025,
    ], source=f"{SRC}、長野県「観光地利用者統計調査」（{sp_ry}年）、総務省「国勢調査」（2020年）")

# ---- 2. 県平均と比べる ----
with ui.card():
    ui.block("県平均と比べる", "数字を選ぶと、県平均・県全体と並べて表示します")
    k = st.selectbox("比べる数字", [mm[1] for mm in METRICS], key="cmp_metric")
    col, label, f, pv, pl = next(mm for mm in METRICS if mm[1] == k)
    ui.chart(compare.bars(cmp, t[col], pv, fmt=f, pref_label=pl,
                          tickformat="+.0%" if "yoy" in col else ".0%" if col in ("kengai", "shuku") else None))
    pts = compare.readout(cmp, t[col], pv, label.replace("※", ""), fmt=f, pref_label=pl)
    ui.readout(pts or [f"{NAME}は、この数字が公表されていません。"],
               source=f"{SRC}。※は長野県「観光地利用者統計調査」。県平均は数字のある市町村の平均")

# ---- 3. 同じ広域 ----
with ui.card():
    ui.block(f"{m.kouiki}広域の市町村", f"観光来訪者数と住民1人あたり（{ly}年）")
    same = t[t.kouiki == m.kouiki].dropna(subset=["visitors"]).sort_values("visitors")
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(y=same.name, x=same.visitors / 1e4, orientation="h",
                               marker_color=[charts.MAIN if c == code else charts.CONTEXT for c in same.index],
                               text=[man(v) for v in same.visitors], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} %{x:,.1f}万人<extra></extra>"))
        charts.layout(fig, height=max(240, 36 * len(same) + 70), title={"text": "観光来訪者数", "font": {"size": 14}})
        fig.update_xaxes(range=[0, same.visitors.max() / 1e4 * 1.35])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    with c2:
        s2 = same.sort_values("per_resident")
        fig = go.Figure(go.Bar(y=s2.name, x=s2.per_resident, orientation="h",
                               marker_color=[charts.MAIN if c == code else charts.CONTEXT for c in s2.index],
                               text=[f"{v:,.0f}人" for v in s2.per_resident], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} 住民1人あたり %{x:,.0f}人<extra></extra>"))
        charts.layout(fig, height=max(240, 36 * len(same) + 70), title={"text": "住民1人あたりの来訪者", "font": {"size": 14}})
        fig.update_xaxes(range=[0, s2.per_resident.max() * 1.35])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    pts = []
    if code in same.index:
        pts.append(f"{m.kouiki}広域の{len(same)}市町村の中で、{NAME}は {len(same) - list(same.index).index(code)}番目に多く、"
                   f"広域の市町村の合計の {me.visitors / same.visitors.sum():.0%} です。")
    if len(same):
        pts.append(f"住民1人あたりの来訪者がいちばん多いのは **{same.loc[same.per_resident.idxmax(), 'name']}**（{same.per_resident.max():,.0f}人）です。")
    ui.readout(pts, source=f"{SRC}、総務省「国勢調査」（2020年）")

# ---- 4. 似た規模 ----
with ui.card():
    ui.block("似た規模の市町村", f"{ly}年の観光来訪者数が近い市町村（前後3つずつ）")
    order = t.dropna(subset=["visitors"]).sort_values("visitors", ascending=False)
    if code in order.index:
        i = list(order.index).index(code)
        near = order.iloc[max(0, i - 3): i + 4]
        st.dataframe(pd.DataFrame({"市町村": near.name, "広域": near.kouiki,
                                   **{label: [f(v) if pd.notna(v) else "—" for v in near[k]] for k, label, f, _, _ in METRICS}}),
                     hide_index=True, use_container_width=True)
        others = near.drop(code)
        ui.readout([
            f"似た規模の市町村の中で、住民1人あたりの来訪者がいちばん多いのは **{others.loc[others.per_resident.idxmax(), 'name']}**（{others.per_resident.max():,.0f}人）です。"
            if others.per_resident.notna().any() else "",
            f"県外の人の割合（※）がいちばん高いのは **{others.loc[others.kengai.idxmax(), 'name']}**（{others.kengai.max():.0%}）です。"
            if others.kengai.notna().any() else "",
        ], source=SRC)
    else:
        st.markdown(f"{NAME}は{ly}年の人数が公表されていない月があるため、似た規模の市町村を選べません。")

ui.sources(["digital", "riyousha", "population"])

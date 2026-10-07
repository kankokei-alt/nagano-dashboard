import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, compare, data, muni, ui
from lib.charts import man

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}を他の市町村と比べる", "県内の順位、選んだ市町村や県平均との比較、同じ広域・似た規模の市町村。", kicker="市町村")
code = muni.picker("compare")
cmp = muni.compare_picker(code, "compare")

muni.require_digital()
t = muni.vtable()
if code not in t.index:
    st.info(f"{NAME}は、デジタル観光統計オープンデータに観光来訪者数がありません。")
    st.stop()
ly, Y, M = t.attrs["year"], t.attrs["Y"], t.attrs["M"]
sp_ry = int(data.riyousha_spots().year.max())
s = muni.table(sp_ry)  # 観光地利用者統計（調査対象の観光地での割合）
t = t.join(s[["kengai", "shuku", "per_visit"]])
me = t.loc[code]
m = muni.master().loc[code]
pa = muni.annual()
pref_s = pa[pa.year == sp_ry][["kennai", "kengai", "higaeri", "shukuhaku", "spend", "total"]].sum()
ytd_pref = t.ytd.sum() / muni.ytd(Y - 1, M).sum() - 1
y = muni.yearly()

# (列, 名前, 書式, 県平均の値, 県平均の呼び方)
METRICS = [
    ("visitors", f"観光来訪者数（{ly}年）", man, t.visitors.mean(), "県平均"),
    ("yoy", f"前年比（{ly}年）", lambda v: charts.signed(v, 1), y.loc[ly].sum() / y.loc[ly - 1].sum() - 1 if ly - 1 in y.index else np.nan, "県全体"),
    ("ytd_yoy", f"{Y}年1〜{M}月の伸び", lambda v: charts.signed(v, 1), ytd_pref, "県全体"),
    ("per_resident", "住民1人あたりの来訪者", lambda v: f"{v:,.0f}人", y.loc[ly].sum() / muni.population().sum(), "県全体"),
    ("kengai", "県外の人の割合※", lambda v: f"{v:.0%}", pref_s.kengai / (pref_s.kennai + pref_s.kengai), "県全体"),
    ("shuku", "泊まりの人の割合※", lambda v: f"{v:.0%}", pref_s.shukuhaku / (pref_s.higaeri + pref_s.shukuhaku), "県全体"),
    ("per_visit", "1人あたり消費額※", lambda v: f"{v:,.0f}円", pref_s.spend / pref_s.total, "県全体"),
]

ui.insight(
    f"{ly}年の{NAME}の観光来訪者数は県内 <b>{muni.rank(t, 'visitors', code)}</b>、前年からの伸びは <b>{muni.rank(t, 'yoy', code)}</b>、"
    f"住民1人あたりの来訪者は {muni.rank(t, 'per_resident', code)}。{Y}年1〜{M}月の伸びは {muni.rank(t, 'ytd_yoy', code)} です。"
)

# ---- 1. 順位 ----
with ui.card():
    ui.block("県内での順位", "77市町村の中で。大きいほうから数えた順位")
    cols = st.columns(4)
    for i, (k, label, f, pv, pl) in enumerate(METRICS):
        if i == 4:
            cols = st.columns(4)
        with cols[i % 4]:
            val = me[k]
            ui.kpi(label, f(val) if pd.notna(val) else "—", f"県内 {muni.rank(t, k, code)}／{pl} {f(pv)}" if pd.notna(pv) else "")
    ui.readout([
        "※ は県の観光地利用者統計調査の、調査対象の観光地での値です（調査対象の観光地がない市町村は順位がつきません）。",
    ], source=f"日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成、長野県「観光地利用者統計調査」（{sp_ry}年）、総務省「国勢調査」（2020年）")

# ---- 2. 選んだ市町村と比べる ----
with ui.card():
    ui.block("選んだ市町村・県平均と比べる", "上の「比べる」で選んだ市町村の数字を並べて表示")
    rows = []
    for c in cmp.all:
        if c in t.index:
            r = t.loc[c]
            rows.append({"市町村": r["name"], **{label: (f(r[k]) if pd.notna(r[k]) else "—") for k, label, f, _, _ in METRICS}})
    if cmp.pref:
        rows.append({"市町村": "県平均・県全体", **{label: (f(pv) if pd.notna(pv) else "—") for _, label, f, pv, _ in METRICS}})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    compare.hint(cmp)
    k = st.selectbox("グラフにする数字", [mm[1] for mm in METRICS], key="cmp_metric")
    col, label, f, pv, pl = next(mm for mm in METRICS if mm[1] == k)
    ui.chart(compare.bars(cmp, t[col], pv, fmt=f, pref_label=pl,
                          tickformat="+.0%" if col in ("yoy", "ytd_yoy") else ".0%" if col in ("kengai", "shuku") else None))
    ui.readout(compare.readout(cmp, t[col], pv, label.replace("※", ""), fmt=f, pref_label=pl),
               source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成。※は長野県「観光地利用者統計調査」")

# ---- 3. 同じ広域 ----
with ui.card():
    ui.block(f"{m.kouiki}広域の市町村", f"観光来訪者数と前年比（{ly}年）")
    same = t[t.kouiki == m.kouiki].sort_values("visitors")
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
        s2 = same.dropna(subset=["yoy"])
        fig = go.Figure(go.Bar(y=s2.name, x=s2.yoy, orientation="h",
                               marker_color=[(charts.MAIN if v >= 0 else charts.SECOND) if c == code else charts.CONTEXT for c, v in s2.yoy.items()],
                               text=[f"{v:+.0%}" for v in s2.yoy], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} 前年比 %{x:+.1%}<extra></extra>"))
        lim = max(s2.yoy.abs().max() * 1.4, 0.1)
        charts.layout(fig, height=max(240, 36 * len(same) + 70), title={"text": "前年比", "font": {"size": 14}})
        fig.update_xaxes(tickformat="+.0%", range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    ui.readout([
        f"{m.kouiki}広域の{len(same)}市町村の中で、{NAME}は {len(same) - list(same.index).index(code)}番目に多く、広域の市町村の合計の {me.visitors / same.visitors.sum():.0%} です。",
        f"広域の中で前年からの伸びがいちばん大きいのは **{s2.loc[s2.yoy.idxmax(), 'name']}**（{s2.yoy.max():+.0%}）です。" if len(s2) else "",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

# ---- 4. 県内の位置 ----
with ui.card():
    ui.block("県内の市町村の中での位置", f"横：{ly}年の前年比、縦：住民1人あたりの来訪者（対数目盛）、円の大きさ：観光来訪者数")
    d = t.dropna(subset=["yoy", "per_resident"])
    lab = set(d.visitors.nlargest(8).index) | set(cmp.all)
    fig = go.Figure()
    for is_me in (False, True):
        p = d[(d.index == code) == is_me]
        fig.add_trace(go.Scatter(
            x=p.yoy, y=p.per_resident, mode="markers+text", text=[r["name"] if c in lab else "" for c, r in p.iterrows()],
            textposition="top center", textfont={"size": 13 if is_me else 10},
            marker={"size": (p.visitors / d.visitors.max()) ** 0.5 * 50 + 6,
                    "color": [charts.MAIN if is_me else (cmp.color(c) if c in cmp.codes else charts.CONTEXT) for c in p.index],
                    "opacity": 1 if is_me else .6, "line": {"color": "white", "width": 2}},
            customdata=list(zip(p.name, p.visitors / 1e4)), showlegend=False,
            hovertemplate="%{customdata[0]}<br>前年比 %{x:+.0%}・住民1人あたり %{y:,.0f}人<br>%{customdata[1]:,.1f}万人<extra></extra>",
        ))
    fig.add_vline(x=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
    charts.layout(fig, height=460)
    fig.update_xaxes(title=f"観光来訪者数の前年比（{ly}年）", tickformat="+.0%")
    fig.update_yaxes(title="住民1人あたりの来訪者（人）", type="log")
    ui.chart(fig)
    ui.readout([
        f"県内の真ん中（中央値）は、前年比 {d.yoy.median():+.0%}・住民1人あたり {d.per_resident.median():,.0f}人です。",
        f"{NAME}は伸びが{'真ん中より大きく' if me.yoy > d.yoy.median() else '真ん中より小さく'}、"
        f"住民1人あたりの来訪者は{'真ん中より多い' if me.per_resident > d.per_resident.median() else '真ん中より少ない'}位置にいます。" if pd.notna(me.yoy) else "",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成、総務省「国勢調査」（2020年）")

# ---- 5. 似た規模 ----
with ui.card():
    ui.block("似た規模の市町村", f"{ly}年の観光来訪者数が近い市町村（前後3つずつ）")
    order = t.sort_values("visitors", ascending=False)
    i = list(order.index).index(code)
    near = order.iloc[max(0, i - 3): i + 4]
    tbl = pd.DataFrame({"市町村": near.name, "広域": near.kouiki,
                        **{label: [f(v) if pd.notna(v) else "—" for v in near[k]] for k, label, f, _, _ in METRICS}})
    st.dataframe(tbl, hide_index=True, use_container_width=True)
    others = near.drop(code)
    ui.readout([
        f"似た規模の市町村の中で、前年からの伸びがいちばん大きいのは **{others.loc[others.yoy.idxmax(), 'name']}**（{others.yoy.max():+.0%}）です。" if others.yoy.notna().any() else "",
        f"住民1人あたりの来訪者がいちばん多いのは **{others.loc[others.per_resident.idxmax(), 'name']}**（{others.per_resident.max():,.0f}人）です。" if others.per_resident.notna().any() else "",
    ], source="日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成")

ui.sources(["digital", "riyousha", "population"])

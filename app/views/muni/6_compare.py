import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, muni, ui
from lib.charts import man

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}を他の市町村と比べる", "県内の順位、同じ広域の市町村、似た規模の市町村との比較。", kicker="市町村")
code = muni.picker("compare")

a = muni.annual()
ry = int(a.year.max())
t = muni.table(ry)
if code not in t.index:
    st.info(f"{NAME}には、県の観光地利用者統計調査の調査対象の観光地がありません。")
    st.stop()
me = t.loc[code]
m = muni.master().loc[code]
METRICS = [("total", "延べ利用者数", lambda v: man(v)), ("vs2019", "2019年比", lambda v: f"{v:+.0%}"),
           ("yoy", "前年比", lambda v: f"{v:+.1%}"), ("kengai", "県外の人の割合", lambda v: f"{v:.0%}"),
           ("shuku", "泊まりの人の割合", lambda v: f"{v:.0%}"), ("per_visit", "1人あたり消費額", lambda v: f"{v:,.0f}円"),
           ("per_resident", "住民1人あたりの利用者", lambda v: f"{v:,.0f}人")]

ui.insight(
    f"{ry}年の{NAME}は、延べ利用者数が県内 <b>{muni.rank(t, 'total', code)}</b>、2019年比の伸びが <b>{muni.rank(t, 'vs2019', code)}</b>、"
    f"県外の人の割合が {muni.rank(t, 'kengai', code)}、1人あたり消費額が {muni.rank(t, 'per_visit', code)} です。"
)

# ---- 1. 順位 ----
with ui.card():
    ui.block("県内での順位", f"{ry}年。調査対象の観光地がある {len(t)} 市町村の中で")
    cols = st.columns(4)
    for i, (k, label, f) in enumerate(METRICS):
        with cols[i % 4]:
            v = me[k]
            ui.kpi(label, f(v) if pd.notna(v) else "—", f"県内 {muni.rank(t, k, code)}／中央値 {f(t[k].median())}")
        if i == 3:
            cols = st.columns(4)
    ui.readout([
        "順位は大きいほうから数えています（例: 2019年比は伸びが大きいほど上位）。",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）、総務省「国勢調査」（2020年）")

# ---- 2. 同じ広域 ----
with ui.card():
    ui.block(f"{m.kouiki}広域の市町村", "延べ利用者数と2019年比")
    same = t[t.kouiki == m.kouiki].sort_values("total")
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(y=same.name, x=same.total / 1e4, orientation="h",
                               marker_color=[charts.MAIN if c == code else charts.CONTEXT for c in same.index],
                               text=[f"{v / 1e4:,.0f}万人" for v in same.total], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} %{x:,.1f}万人<extra></extra>"))
        charts.layout(fig, height=max(240, 36 * len(same) + 70), title={"text": f"延べ利用者数（{ry}年）", "font": {"size": 14}})
        fig.update_xaxes(range=[0, same.total.max() / 1e4 * 1.35])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    with c2:
        s2 = same.dropna(subset=["vs2019"])
        fig = go.Figure(go.Bar(y=s2.name, x=s2.vs2019, orientation="h",
                               marker_color=[(charts.MAIN if v >= 0 else charts.SECOND) if c == code else charts.CONTEXT for c, v in s2.vs2019.items()],
                               text=[f"{v:+.0%}" for v in s2.vs2019], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} 2019年比 %{x:+.1%}<extra></extra>"))
        lim = max(s2.vs2019.abs().max() * 1.35, 0.2)
        charts.layout(fig, height=max(240, 36 * len(same) + 70), title={"text": "2019年比", "font": {"size": 14}})
        fig.update_xaxes(tickformat="+.0%", range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    ui.readout([
        f"{m.kouiki}広域では {NAME} が {len(same) - list(same.index).index(code)}番目に多く、広域全体の {me.total / same.total.sum():.0%} を占めます。",
        f"広域の中で2019年比の伸びがいちばん大きいのは **{t.loc[s2.vs2019.idxmax(), 'name']}**（{s2.vs2019.max():+.0%}）です。" if len(s2) else "",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

# ---- 3. 県内の位置 ----
with ui.card():
    ui.block("県内の市町村の中での位置", "横：2019年比の伸び、縦：泊まりの人の割合、円の大きさ：延べ利用者数")
    d = t.dropna(subset=["vs2019", "shuku"])
    lab = set(d.total.nlargest(8).index) | {code}
    fig = go.Figure()
    for is_me in (False, True):
        p = d[(d.index == code) == is_me]
        fig.add_trace(go.Scatter(
            x=p.vs2019, y=p.shuku, mode="markers+text", text=[r["name"] if c in lab else "" for c, r in p.iterrows()],
            textposition="top center", textfont={"size": 13 if is_me else 10},
            marker={"size": (p.total / d.total.max()) ** 0.5 * 50 + 6, "color": charts.MAIN if is_me else charts.CONTEXT,
                    "opacity": 1 if is_me else .55, "line": {"color": "white", "width": 2}},
            customdata=list(zip(p.name, p.total / 1e4)), showlegend=False,
            hovertemplate="%{customdata[0]}<br>2019年比 %{x:+.0%}・泊まり %{y:.0%}<br>%{customdata[1]:,.1f}万人<extra></extra>",
        ))
    fig.add_vline(x=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
    charts.layout(fig, height=460)
    lo, hi = d.vs2019.quantile(0.03), d.vs2019.quantile(0.95)  # 極端な値で全体がつぶれないよう、表示は大半が入る範囲に
    lo, hi = min(lo, me.vs2019 if pd.notna(me.vs2019) else lo), max(hi, me.vs2019 if pd.notna(me.vs2019) else hi)
    pad = (hi - lo) * 0.08
    out = d[(d.vs2019 < lo - pad) | (d.vs2019 > hi + pad)]
    fig.update_xaxes(title="延べ利用者数 2019年比", tickformat="+.0%", range=[lo - pad, hi + pad])
    fig.update_yaxes(title="泊まりの人の割合", tickformat=".0%")
    ui.chart(fig)
    if len(out):
        n19 = a[a.year == 2019].set_index("municipality_code").spots
        st.caption("グラフの範囲の外: " + "、".join(
            f"{r['name']}（{r.vs2019:+.0%}、調査対象の観光地 2019年 {int(n19.get(c, 0))}か所→{ry}年 {int(r.spots)}か所）"
            for c, r in out.iterrows()) + "。")
    ui.readout([
        f"県内の真ん中（中央値）は、2019年比 {d.vs2019.median():+.0%}・泊まりの人の割合 {d.shuku.median():.0%} です。",
        f"{NAME}は伸びが{'真ん中より大きく' if me.vs2019 > d.vs2019.median() else '真ん中より小さく'}、"
        f"泊まりの割合は{'真ん中より高い' if me.shuku > d.shuku.median() else '真ん中より低い'}位置にいます。" if pd.notna(me.vs2019) else "",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

# ---- 4. 似た規模 ----
with ui.card():
    ui.block("似た規模の市町村", "延べ利用者数が近い市町村（前後3つずつ）")
    order = t.sort_values("total", ascending=False)
    i = list(order.index).index(code)
    near = order.iloc[max(0, i - 3): i + 4]
    tbl = pd.DataFrame({
        "市町村": near.name, "広域": near.kouiki, "延べ利用者数": [man(v) for v in near.total],
        "2019年比": [f"{v:+.0%}" if pd.notna(v) else "—" for v in near.vs2019],
        "県外の人": [f"{v:.0%}" for v in near.kengai], "泊まりの人": [f"{v:.0%}" for v in near.shuku],
        "1人あたり消費": [f"{v:,.0f}円" for v in near.per_visit], "観光地の数": near.spots.astype(int),
    })
    st.dataframe(tbl, hide_index=True, use_container_width=True)
    others = near.drop(code)
    ui.readout([
        f"似た規模の市町村の中で、2019年比の伸びがいちばん大きいのは **{t.loc[others.vs2019.idxmax(), 'name']}**（{others.vs2019.max():+.0%}）、"
        f"1人あたり消費額がいちばん高いのは **{t.loc[others.per_visit.idxmax(), 'name']}**（{others.per_visit.max():,.0f}円）です。" if others.vs2019.notna().any() else "",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

ui.sources(["riyousha"])

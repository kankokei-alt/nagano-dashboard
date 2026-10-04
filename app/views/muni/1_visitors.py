import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, muni, ui
from lib.charts import man, updown

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}に誰が来ている？", "県内の人か県外の人か、日帰りか泊まりか。県全体と比べて特徴を見ます。", kicker="市町村")
code = muni.picker("visitors")

a = muni.annual()
mine = a[a.municipality_code == code].set_index("year")
if mine.empty:
    st.info(f"{NAME}には、県の観光地利用者統計調査の調査対象の観光地がありません。")
    st.stop()
ry = int(mine.index.max())
cur = mine.loc[ry]
pref = a.groupby("year")[["kennai", "kengai", "higaeri", "shukuhaku", "total"]].sum()
sp = data.riyousha_spots()
spots = sp[(sp.municipality_code == code) & (sp.year == ry)].copy()
t = muni.table(ry)


def share(d, a_, b_):
    return d[b_] / (d[a_] + d[b_])


kg, kg_p = share(cur, "kennai", "kengai"), share(pref.loc[ry], "kennai", "kengai")
sh, sh_p = share(cur, "higaeri", "shukuhaku"), share(pref.loc[ry], "higaeri", "shukuhaku")
ui.insight(
    f"{ry}年に{NAME}の観光地を訪れた人のうち、<b>県外の人は{kg:.0%}</b>（県全体 {kg_p:.0%}）、"
    f"<b>泊まりの人は{sh:.0%}</b>（県全体 {sh_p:.0%}）でした。"
    + ("県全体より県外の人が多く、" if kg > kg_p + 0.02 else "県全体より県内の人が多く、" if kg < kg_p - 0.02 else "県外の人の割合は県全体と同じくらいで、")
    + ("泊まりの割合も高い観光地です。" if sh > sh_p + 0.02 else "日帰りが中心です。" if sh < sh_p - 0.02 else "泊まりの割合も県全体並みです。")
)

# ---- 1. 構成 ----
with ui.card():
    ui.block("来訪者の構成", f"{ry}年。県内・県外、日帰り・泊まりの割合を県全体と比較")
    rows = [(f"{NAME}・県内/県外", 1 - kg, kg), ("県全体・県内/県外", 1 - kg_p, kg_p),
            (f"{NAME}・日帰り/泊まり", 1 - sh, sh), ("県全体・日帰り/泊まり", 1 - sh_p, sh_p)]
    fig = go.Figure()
    for i, (label, color) in enumerate([("県内・日帰り", charts.MAIN), ("県外・泊まり", charts.SECOND)]):
        vals = [r[1 + i] for r in rows]
        fig.add_trace(go.Bar(y=[r[0] for r in rows], x=vals, orientation="h", name=label.replace("・", "／"), marker_color=color,
                             marker_line={"color": "white", "width": 2}, text=[f"{v:.0%}" for v in vals],
                             textposition="inside", insidetextanchor="middle", textfont={"color": "white"},
                             hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
    charts.layout(fig, height=280, barmode="stack", legend_traceorder="normal")
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(autorange="reversed", showgrid=False)
    ui.chart(fig)
    ui.readout([
        f"県外の人の割合は県内 {muni.rank(t, 'kengai', code)}、泊まりの人の割合は {muni.rank(t, 'shuku', code)} です。",
        f"延べ人数にすると、県外の人 {man(cur.kengai)}・県内の人 {man(cur.kennai)}、泊まり {man(cur.shukuhaku)}・日帰り {man(cur.higaeri)} です。",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

# ---- 2. 推移 ----
with ui.card():
    ui.block("県外の人・泊まりの人の割合の推移", "年ごと。点線は県全体")
    fig = go.Figure()
    for (x, y_, label), color in zip([("kennai", "kengai", "県外の人"), ("higaeri", "shukuhaku", "泊まりの人")], [charts.SECOND, charts.MAIN]):
        v, vp = share(mine, x, y_), share(pref, x, y_)
        fig.add_trace(go.Scatter(x=v.index, y=v, name=f"{NAME}・{label}", mode="lines+markers", line={"color": color, "width": 3},
                                 hovertemplate=f"%{{x}}年 {label}の割合 %{{y:.1%}}<extra></extra>"))
        fig.add_trace(go.Scatter(x=vp.index, y=vp, name=f"県全体・{label}", mode="lines", line={"color": color, "width": 1.5, "dash": "dot"},
                                 hovertemplate=f"%{{x}}年 県全体 %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=340, hovermode="x unified")
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    fig.update_xaxes(dtick=1)
    ui.chart(fig)
    kgs, shs = share(mine, "kennai", "kengai"), share(mine, "higaeri", "shukuhaku")
    ui.readout([
        f"県外の人の割合は {kgs.idxmin()}年が最も低く（{kgs.min():.0%}）、{kgs.idxmax()}年が最も高い（{kgs.max():.0%}）です。",
        f"泊まりの人の割合は{kgs.index.min()}年の {shs.iloc[0]:.0%} から {ry}年の {shs.iloc[-1]:.0%} へ{'上がりました' if shs.iloc[-1] > shs.iloc[0] + 0.01 else '下がりました' if shs.iloc[-1] < shs.iloc[0] - 0.01 else '、ほぼ同じです'}。",
    ], source="長野県「観光地利用者統計調査」")

# ---- 3. 観光地別 ----
with ui.card():
    ui.block("観光地ごとの、県外の人・泊まりの人の割合", f"{ry}年。円の大きさは延べ利用者数")
    spots["kg"] = spots.kengai / (spots.kennai + spots.kengai)
    spots["sh"] = spots.shukuhaku / (spots.higaeri + spots.shukuhaku)
    s2 = spots.dropna(subset=["kg", "sh"])
    fig = go.Figure(go.Scatter(
        x=s2.kg, y=s2.sh, mode="markers+text", text=s2.spot, textposition="top center", textfont={"size": 11},
        marker={"size": (s2.total / s2.total.max()) ** 0.5 * 46 + 8, "color": charts.MAIN, "opacity": .75, "line": {"color": "white", "width": 2}},
        customdata=s2.total / 1e4, hovertemplate="<b>%{text}</b><br>県外 %{x:.0%}・泊まり %{y:.0%}<br>%{customdata:,.1f}万人<extra></extra>",
    ))
    fig.add_vline(x=kg_p, line={"color": charts.CONTEXT, "dash": "dot"})
    fig.add_hline(y=sh_p, line={"color": charts.CONTEXT, "dash": "dot"})
    charts.layout(fig, height=420, showlegend=False)
    fig.update_xaxes(title="県外の人の割合", tickformat=".0%", range=[-0.05, 1.05])
    fig.update_yaxes(title="泊まりの人の割合", tickformat=".0%", range=[-0.05, 1.05])
    ui.chart(fig)
    st.caption("点線は県全体の割合。右上ほど「県外から泊まりで来る人」が多い観光地です。")
    hi = s2[(s2.kg > kg_p) & (s2.sh > sh_p)]
    ui.readout([
        f"県外の人の割合がいちばん高い観光地は **{s2.loc[s2.kg.idxmax(), 'spot']}**（{s2.kg.max():.0%}）、泊まりの割合がいちばん高いのは **{s2.loc[s2.sh.idxmax(), 'spot']}**（{s2.sh.max():.0%}）です。",
        (f"県全体より県外の人も泊まりの人も多い観光地: {'・'.join(hi.spot)}。" if len(hi) else "県全体より県外の人も泊まりの人も多い観光地はありません。"),
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

st.info("国籍別（海外のお客さま）の数は市町村ごとには公表されていません。宿泊統計の県内5エリア別の外国人宿泊は「エリア・宿泊・気象」で見られます。")
ui.sources(["riyousha"])

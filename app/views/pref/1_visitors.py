import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui
from lib.charts import man, updown, yen

ui.setup("誰が来ている？", "県内・県外・海外、日帰りか泊まりか、観光か仕事か。")

ir = data.irikomi()
iy = int(ir.year.max())
d = ir[(ir.stay != "計") & (ir.measure != "unit_price")].copy()
d["who"] = "海外の人"
d.loc[(d.purpose != "訪日外国人") & (d.origin == "県内"), "who"] = "県内の人"
d.loc[(d.purpose != "訪日外国人") & (d.origin == "県外"), "who"] = "県外の人"
WHO = [("県内の人", charts.MAIN), ("県外の人", charts.SECOND), ("海外の人", charts.THIRD)]
year = d[d.period == "年計"]
cur = year[year.year == iy]
share = cur.groupby(["measure", "who"]).value.sum().unstack()
share = share.div(share.sum(axis=1), axis=0)
by_year = year[year.measure == "visitors"].groupby(["year", "who"]).value.sum().unstack()

ui.insight(
    f"{iy}年に長野県を訪れた人のうち、人数では <b>県外の人が{share.loc['visitors', '県外の人']:.0%}</b>、"
    f"県内の人が{share.loc['visitors', '県内の人']:.0%}、海外の人が{share.loc['visitors', '海外の人']:.0%}でした。"
    f"使ったお金で見ると県外の人が <b>{share.loc['spend', '県外の人']:.0%}</b>、海外の人が {share.loc['spend', '海外の人']:.0%} で、"
    "遠くから来る人ほど1人あたり多くのお金を使っています。"
)

# ---- 1. 人数とお金の内訳 ----
with ui.card():
    ui.block("来訪者の構成", "県内・県外・海外別の、人数と消費額の割合")
    rows = {"visitors": "人数", "spend": "使ったお金"}
    fig = go.Figure()
    for grp, color in WHO:
        v = share[grp].reindex(list(rows))
        fig.add_trace(go.Bar(
            y=[rows[k] for k in v.index], x=v.values, name=grp, orientation="h", marker_color=color,
            marker_line={"color": "white", "width": 2}, text=[f"{grp}<br>{x:.0%}" if x > 0.08 else f"{x:.0%}" for x in v.values],
            textposition="inside", insidetextanchor="middle", textfont={"color": "white", "size": 13},
            hovertemplate=f"{grp}<br>%{{y}}の %{{x:.1%}}<extra></extra>",
        ))
    charts.layout(fig, height=230, barmode="stack", legend_traceorder="normal")
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(autorange="reversed", showgrid=False)
    ui.chart(fig)
    per = cur.groupby(["measure", "who"]).value.sum().unstack()
    per = per.loc["spend"] / per.loc["visitors"]
    ui.readout([
        f"1人あたりに直すと、県内の人は **{per['県内の人']:,.0f}円**、県外の人は **{per['県外の人']:,.0f}円**、海外の人は **{per['海外の人']:,.0f}円** です。",
        f"海外の人は人数では {share.loc['visitors', '海外の人']:.0%} ですが、1人あたりでは県内の人の約 {per['海外の人'] / per['県内の人']:.0f} 倍を使っています。",
    ], source=f"長野県「観光入込客統計」（観光庁 共通基準, {iy}年）。観光目的とビジネス目的の合計。人数は実人数")

# ---- 2. 移り変わり ----
with ui.card():
    ui.block("来訪者数の推移", "県内・県外・海外別、年ごと（実人数）")
    fig = go.Figure()
    for grp, color in WHO:
        v = by_year[grp].dropna() / 1e4
        fig.add_trace(go.Scatter(x=v.index, y=v.values, name=grp, mode="lines+markers", line={"color": color, "width": 2.5},
                                 marker={"size": 7}, hovertemplate=f"{grp} %{{x}}年 %{{y:,.0f}}万人<extra></extra>"))
        fig.add_annotation(x=v.index[-1], y=v.iloc[-1], text=f"<b>{grp}</b>", showarrow=False, xanchor="left", xshift=8)
    charts.layout(fig, height=340, hovermode="x unified")
    fig.update_yaxes(title="万人（実人数）", rangemode="tozero")
    fig.update_xaxes(dtick=1, range=[by_year.index.min() - 0.5, by_year.index.max() + 1.5])
    ui.chart(fig)
    chg19 = by_year.loc[iy] / by_year.loc[2019] - 1
    ui.readout([
        f"コロナ前の2019年と比べると、県内の人は{updown(chg19['県内の人'])}、県外の人は{updown(chg19['県外の人'])}、海外の人は{updown(chg19['海外の人'])}です。",
        f"いちばん戻りが{'早い' if chg19.max() > 0 else '進んでいる'}のは **{chg19.idxmax()}**、遅れているのは **{chg19.idxmin()}** です。",
    ], source="長野県「観光入込客統計」。2010〜2015年のビジネス目的、2017・2018年の入込客数は参考値")

# ---- 3. 泊まるか日帰りか ----
with ui.card():
    ui.block("宿泊の割合と消費単価", "泊まった人の割合と、1人あたりの消費額")
    v = cur[cur.measure == "visitors"].groupby(["who", "stay"]).value.sum().unstack()
    stay_share = (v["宿泊"] / v.sum(axis=1)).reindex([w for w, _ in WHO])
    up = cur.groupby(["measure", "stay"]).value.sum().unstack()
    up = up.loc["spend"] / up.loc["visitors"]
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure(go.Bar(
            x=stay_share.index, y=stay_share.values, marker_color=[c for _, c in WHO],
            text=[f"{x:.0%}" for x in stay_share.values], textposition="outside", cliponaxis=False,
            hovertemplate="%{x}: 泊まった人の割合 %{y:.1%}<extra></extra>",
        ))
        charts.layout(fig, height=300, title={"text": "泊まった人の割合", "font": {"size": 14}})
        fig.update_yaxes(tickformat=".0%", range=[0, 1.1])
        ui.chart(fig)
    with c2:
        st.metric("泊まりの人の1人あたり消費", f"{up['宿泊']:,.0f}円")
        st.metric("日帰りの人の1人あたり消費", f"{up['日帰り']:,.0f}円")
    ui.readout([
        f"県内の人で泊まったのは **{stay_share['県内の人']:.0%}** だけで、ほとんどが日帰りです。県外の人は {stay_share['県外の人']:.0%}、海外の人は {stay_share['海外の人']:.0%} が泊まっています。",
        f"泊まりの人は日帰りの人の約 **{up['宿泊'] / up['日帰り']:.1f} 倍** のお金を使います。日帰りの人に1泊してもらうことの効果は大きいと言えます。",
    ], source=f"長野県「観光入込客統計」（{iy}年）")

# ---- 4. 季節ごと ----
with ui.card():
    ui.block("来訪者の季節性", "県内・県外・海外それぞれの1年を100%とした、季節ごとの割合")
    q = d[(d.year == iy) & (d.period != "年計") & (d.measure == "visitors")].groupby(["period", "who"]).value.sum().unstack()
    QL = {"Q1": "1〜3月", "Q2": "4〜6月", "Q3": "7〜9月", "Q4": "10〜12月"}
    qs = q / q.sum()  # それぞれの1年を100%とした割合
    fig = go.Figure()
    for grp, color in WHO:
        fig.add_trace(go.Bar(x=[QL[p] for p in qs.index], y=qs[grp], name=grp, marker_color=color,
                             marker_line={"color": "white", "width": 2}, text=[f"{v:.0%}" for v in qs[grp]], textposition="outside",
                             customdata=q[grp] / 1e4,
                             hovertemplate=f"{grp} %{{x}}: 1年の %{{y:.1%}}（%{{customdata:,.0f}}万人）<extra></extra>"))
    fig.add_hline(y=0.25, line={"color": "rgba(128,128,128,.6)", "dash": "dot", "width": 1})
    charts.layout(fig, height=330, barmode="group", bargap=0.25, legend_traceorder="normal")
    fig.update_yaxes(tickformat=".0%", title="1年に占める割合", range=[0, qs.values.max() * 1.2])
    ui.chart(fig)
    st.caption("点線（25%）は、1年を通して同じだけ来た場合の目安です。")
    ui.readout([
        f"**{g}** がいちばん多いのは {QL[qs[g].idxmax()]}（1年の {qs[g].max():.0%}）、少ないのは {QL[qs[g].idxmin()]}（{qs[g].min():.0%}）です。"
        for g, _ in WHO
    ] + [
        f"季節による差がいちばん大きいのは **{(qs.max() - qs.min()).idxmax()}** です。",
    ], source=f"長野県「観光入込客統計」（{iy}年）")

# ---- 5. 観光とビジネス ----
with ui.card():
    ui.block("ビジネス目的の来訪者", "仕事で訪れた人の数と、1人あたりの消費額（年ごと）")
    dom = year[(year.purpose != "訪日外国人")].groupby(["year", "measure", "purpose"]).value.sum().unstack()
    bz = dom["ビジネス目的"].unstack()
    tr = dom["観光目的"].unstack()
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(x=bz.index, y=bz.visitors / 1e4, marker_color=charts.MAIN,
                               hovertemplate="%{x}年 ビジネス目的 %{y:,.0f}万人<extra></extra>"))
        charts.layout(fig, height=280, title={"text": "ビジネス目的で訪れた人（万人）", "font": {"size": 14}}, bargap=0.25)
        fig.update_xaxes(dtick=2)
        ui.chart(fig)
    with c2:
        fig = go.Figure()
        for v, label, color in [(bz.spend / bz.visitors, "ビジネス目的", charts.MAIN), (tr.spend / tr.visitors, "観光目的", charts.CONTEXT)]:
            fig.add_trace(go.Scatter(x=v.index, y=v, name=label, mode="lines+markers", line={"color": color, "width": 2.5},
                                     hovertemplate=f"%{{x}}年 {label} 1人あたり %{{y:,.0f}}円<extra></extra>"))
        charts.layout(fig, height=280, title={"text": "1人あたりの消費額（円）", "font": {"size": 14}}, hovermode="x unified")
        fig.update_xaxes(dtick=2)
        fig.update_yaxes(rangemode="tozero")
        ui.chart(fig)
    bv = cur[(cur.measure == "visitors") & (cur.purpose != "訪日外国人")].groupby(["purpose", "stay"]).value.sum().unstack()
    bstay = bv["宿泊"] / bv.sum(axis=1)
    bp, tp = bz.spend[iy] / bz.visitors[iy], tr.spend[iy] / tr.visitors[iy]
    ui.readout([
        f"{iy}年にビジネス目的で訪れた人は **{man(bz.visitors[iy])}**（前年より{updown(bz.visitors[iy] / bz.visitors[iy - 1] - 1)}、2019年より{updown(bz.visitors[iy] / bz.visitors[2019] - 1)}）。",
        f"1人あたりの消費額は、ビジネス目的 **{bp:,.0f}円**、観光目的 {tp:,.0f}円 です。"
        f"ビジネス目的の人は {bstay['ビジネス目的']:.0%} が泊まっています（観光目的は {bstay['観光目的']:.0%}）。",
    ], source="長野県「観光入込客統計」。国内からの来訪者。2010〜2015年のビジネス目的、2017・2018年の入込客数は参考値")

# ---- 6. 宿泊者の県内・県外（月ごと） ----
with ui.card():
    ui.block("宿泊者の県外比率", "延べ宿泊者に占める県外居住者の割合（月別）")
    res = data.shukuhaku_residence()
    res["share"] = res.kengai / res.total
    ry = int(res.ym.dt.year.max())
    fig = go.Figure()
    for y, label, color, dash in [(2019, "2019年（コロナ前）", charts.CONTEXT, "dot"), (ry, f"{ry}年", charts.MAIN, "solid")]:
        v = res[res.ym.dt.year == y]
        fig.add_trace(go.Scatter(x=v.ym.dt.month, y=v.share, name=label, mode="lines+markers",
                                 line={"color": color, "width": 3 if y == ry else 2, "dash": dash},
                                 hovertemplate=f"{label} %{{x}}月 県外の人 %{{y:.1%}}<extra></extra>"))
    charts.layout(fig, height=300, hovermode="x unified")
    fig.update_xaxes(tickvals=list(range(1, 13)), ticktext=[f"{m}月" for m in range(1, 13)])
    fig.update_yaxes(tickformat=".0%", title="県外の人の割合")
    ui.chart(fig)
    cy = res[res.ym.dt.year == ry].set_index(res[res.ym.dt.year == ry].ym.dt.month).share
    yearly = res.groupby(res.ym.dt.year).apply(lambda x: x.kengai.sum() / x.total.sum())
    ui.readout([
        f"{ry}年は、泊まった人の **{yearly[ry]:.0%}** が県外の人でした（2019年 {yearly[2019]:.0%}）。",
        f"県外の人の割合がいちばん高いのは **{cy.idxmax()}月**（{cy.max():.0%}）、いちばん低いのは **{cy.idxmin()}月**（{cy.min():.0%}）です。",
        f"県内の人の割合がいちばん高かった年は {yearly.idxmin()}年（県外 {yearly.min():.0%}）で、県民割などで県内の旅行が増えた時期にあたります。"
        if yearly.idxmin() in (2020, 2021, 2022) else "",
    ], source="観光庁「宿泊旅行統計調査」（居住地別, 年の確定値）")

    st.info("「東京から何人・愛知から何人」といった、住んでいる都道府県ごとの内訳は、いま取り込んでいるデータにはありません。"
            "取れる統計を確認して、取り込めたらこのページに加えます。", icon="📌")

ui.sources(["irikomi", "shukuhaku"])

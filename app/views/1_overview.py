import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, maps, ui
from lib.charts import man, pct, updown, yen

ui.setup("長野県を俯瞰する", "県全体の観光の「いま」を、4つの数字と地図でつかむページです。")

# ---- 宿泊（月次） ----
s = data.shukuhaku()
s["foreign_share"] = s.foreign / s.guests
last = s.index.max()
prev = last - pd.DateOffset(years=1)
pre = last.replace(year=2019)
cur, ly, cv = s.loc[last], s.loc[prev], s.loc[pre]
ym = f"{last.year}年{last.month}月"
is_prelim = cur.status == "速報"

# ---- 入込客・観光消費額（年次） ----
ir = data.irikomi()
ann = ir[(ir.period == "年計") & (ir.stay == "計")].groupby(["year", "measure"]).value.sum().unstack()
iy = int(ann.index.max())
spend, spend_ly = ann.loc[iy, "spend"], ann.loc[iy - 1, "spend"]
visitors, visitors_ly = ann.loc[iy, "visitors"], ann.loc[iy - 1, "visitors"]

ui.insight(
    f"{ym}の延べ宿泊者数は <b>{man(cur.guests, '人泊')}</b> で、前年同月より{updown(cur.guests / ly.guests - 1)}、"
    f"コロナ前（2019年{last.month}月）と比べると{updown(cur.guests / cv.guests - 1)}でした。"
    f"泊まった人のうち外国人は <b>{cur.foreign_share:.0%}</b>（前年同月 {ly.foreign_share:.0%}）です。"
    f"<br>年間で見ると、{iy}年の観光消費額は <b>{yen(spend)}</b> で前年より{updown(spend / spend_ly - 1)}"
    + (f"。県を訪れた人の数（実人数）は{updown(visitors / visitors_ly - 1)}なので、1人あたりの消費が伸びています。"
       if spend / spend_ly > visitors / visitors_ly + 0.02 else
       f"、県を訪れた人の数（実人数）は{updown(visitors / visitors_ly - 1)}でした。")
)

cols = st.columns(4)
with cols[0]:
    ui.kpi(f"延べ宿泊者数（{ym}）", man(cur.guests, "人泊"),
           f"前年同月比 {pct(cur.guests / ly.guests - 1)}／2019年比 {pct(cur.guests / cv.guests - 1)}")
with cols[1]:
    ui.kpi(f"客室稼働率（{ym}）", f"{cur.occupancy:.1f}%",
           f"前年同月差 {cur.occupancy - ly.occupancy:+.1f}pt／2019年 {cv.occupancy:.1f}%")
with cols[2]:
    ui.kpi(f"外国人宿泊者の割合（{ym}）", f"{cur.foreign_share:.1%}",
           f"前年同月差 {(cur.foreign_share - ly.foreign_share) * 100:+.1f}pt")
with cols[3]:
    ui.kpi(f"観光消費額（{iy}年）", yen(spend), f"前年比 {pct(spend / spend_ly - 1)}")
if is_prelim:
    st.caption(f"※ {last.year}年の宿泊の数字は速報値です。{last.year}年1月分から調査の区分け（層化基準）が変わったため、"
               "前年との比較には見直しの影響が含まれることがあります（観光庁）。")

# ---- 地図: 観光地の延利用者数 ----
sp = data.riyousha_spots()
ry = int(sp.year.max())
by_muni = sp[sp.year == ry].groupby("municipality_code").total.sum()
top = by_muni.sort_values(ascending=False)
g = data.municipalities()
names = g.set_index("code").name
st.subheader("どこに人が来ているか")
st.markdown(
    f"{ry}年の観光地の延べ利用者数は、**{names[top.index[0]]}・{names[top.index[1]]}・{names[top.index[2]]}** の3市町で"
    f"県全体の **{top.iloc[:3].sum() / top.sum():.0%}** を占めます。色が濃いほど多くの人が訪れています。"
)
st.plotly_chart(
    maps.municipality_map(g, outlines=data.kouiki(), values=by_muni.to_dict(),
                          value_label=f"{ry}年の延べ利用者数", fmt=man),
    use_container_width=True,
)
st.caption(f"太線は10広域の境界です。灰色は県の調査で対象の観光地がない市町村です。"
           f"出典: 長野県「観光地利用者統計調査」（{ry}年）。{maps.ATTRIBUTION}")

c1, c2 = st.columns(2)

# ---- 季節の波 ----
with c1:
    st.subheader("季節ごとの波")
    fig = go.Figure()
    lines = [(2019, "2019年（コロナ前）", charts.CONTEXT, "dot"),
             (last.year - 1, f"{last.year - 1}年", charts.CONTEXT, "solid"),
             (last.year, f"{last.year}年", charts.MAIN, "solid")]
    for y, label, color, dash in lines:
        d = s[s.index.year == y]
        fig.add_trace(go.Scatter(
            x=d.index.month, y=d.guests / 1e4, name=label, mode="lines+markers",
            line={"color": color, "width": 3 if y == last.year else 2, "dash": dash},
            marker={"size": 8 if y == last.year else 6},
            hovertemplate=f"{label} %{{x}}月<br>%{{y:,.0f}}万人泊<extra></extra>",
        ))
        if y == last.year:  # 比べる系列は凡例で示し、いまの年だけ線の端に名前を出す
            fig.add_annotation(x=d.index.month[-1], y=d.guests.iloc[-1] / 1e4, text=f"<b>{label}</b>",
                               showarrow=False, xanchor="left", xshift=10, font={"size": 13})
    charts.layout(fig, height=360, hovermode="x unified")
    fig.update_xaxes(tickvals=list(range(1, 13)), ticktext=[f"{m}月" for m in range(1, 13)], range=[0.6, 12.6])
    fig.update_yaxes(title="延べ宿泊者数（万人泊）", rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True)
    full = s[s.index.year == last.year - 1]
    winter = full[full.index.month.isin([12, 1, 2])]
    st.caption(f"{last.year - 1}年にいちばん多かったのは{full.guests.idxmax().month}月。"
               f"外国人は冬（12〜2月）の3か月に年間の {winter.foreign.sum() / full.foreign.sum():.0%} が集中し、"
               "スキーシーズンを支えています。出典: 観光庁「宿泊旅行統計調査」")

# ---- どこから来ているか ----
with c2:
    st.subheader("どこから来ているか")
    yr = ir[(ir.year == iy) & (ir.period == "年計") & (ir.stay != "計") & (ir.measure != "unit_price")].copy()
    yr["group"] = yr.purpose.where(yr.purpose == "訪日外国人", "県外の人")
    yr.loc[(yr.purpose != "訪日外国人") & (yr.origin == "県内"), "group"] = "県内の人"
    yr.loc[yr.group == "訪日外国人", "group"] = "海外からの人"
    share = yr.groupby(["measure", "group"]).value.sum().unstack()
    share = share.div(share.sum(axis=1), axis=0)
    order = [("県内の人", charts.MAIN, "white"), ("県外の人", charts.SECOND, "white"),
             ("海外からの人", charts.THIRD, "#0b0b0b")]
    rows = {"visitors": "人数", "spend": "使ったお金"}
    fig = go.Figure()
    for grp, color, ink in order:
        v = share[grp].reindex(list(rows))
        fig.add_trace(go.Bar(
            y=[rows[k] for k in v.index], x=v.values, name=grp, orientation="h", marker_color=color,
            marker_line={"color": "white", "width": 2},
            text=[f"{x:.0%}" for x in v.values], textposition="inside", insidetextanchor="middle",
            textfont={"color": ink, "size": 14},
            hovertemplate=f"{grp}<br>%{{y}}の %{{x:.1%}}<extra></extra>",
        ))
    charts.layout(fig, height=260, barmode="stack", legend_traceorder="normal")
    fig.update_xaxes(tickformat=".0%", range=[0, 1], showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    st.plotly_chart(fig, use_container_width=True)
    f_v, f_s = share.loc["visitors", "海外からの人"], share.loc["spend", "海外からの人"]
    k_v, k_s = share.loc["visitors", "県外の人"], share.loc["spend", "県外の人"]
    st.markdown(
        f"海外からの人は人数では **{f_v:.0%}** ですが、使ったお金では **{f_s:.0%}**。"
        f"県外の人も人数 {k_v:.0%} に対してお金は {k_s:.0%} で、"
        "**泊まりがけで来る遠方の人ほど、地域にお金を落としています。**"
    )
    st.caption(f"出典: 長野県「観光入込客統計」（観光庁 共通基準, {iy}年）。人数は実人数、観光目的とビジネス目的の合計。")

# ---- 長い目で見ると ----
with st.expander("長い目で見ると（2011年からの延べ宿泊者数）"):
    a = s[s.index.year < last.year].groupby(s.index.year[s.index.year < last.year])[["japanese", "foreign"]].sum()
    fig = go.Figure()
    for col, label, color in [("japanese", "日本人", charts.MAIN), ("foreign", "外国人", charts.SECOND)]:
        fig.add_trace(go.Bar(x=a.index, y=a[col] / 1e4, name=label, marker_color=color,
                             marker_line={"color": "white", "width": 1},
                             hovertemplate=f"%{{x}}年 {label} %{{y:,.0f}}万人泊<extra></extra>"))
    charts.layout(fig, height=320, barmode="stack", bargap=0.25)
    fig.update_yaxes(title="万人泊")
    st.plotly_chart(fig, use_container_width=True)
    best = a.sum(axis=1).idxmax()
    normal = a.sum(axis=1).drop([2020, 2021, 2022], errors="ignore")
    st.markdown(
        f"コロナ禍（2020〜22年）を除くと、延べ宿泊者数は年 {man(normal.min(), '人泊')}〜{man(normal.max(), '人泊')} で推移し、"
        f"{best}年が最多でした。"
        f"外国人は 2011年の {man(a.foreign.iloc[0], '人泊')} から {a.index[-1]}年には "
        f"{man(a.foreign.iloc[-1], '人泊')} に増え、全体の {a.foreign.iloc[-1] / a.sum(axis=1).iloc[-1]:.0%} になりました。"
    )

ui.sources(["boundaries", "shukuhaku", "irikomi", "riyousha"])

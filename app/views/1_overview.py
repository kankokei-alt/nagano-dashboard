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


# ---- 全国の訪日客（JNTO, 先行指標） ----
jn = data.jnto()
J = jn[jn.kind.isin(["total", "country", "sub"])].pivot_table(index="ym", columns="country", values="value")
j_status = jn[jn.kind == "total"].set_index("ym").status
jl = J.index.max()
j_yoy = J / J.shift(12, freq="MS").reindex(J.index)
nat_all = data.shukuhaku_nationality()
nat_y = int(nat_all.ym.dt.year.max())
w = (nat_all[nat_all.ym.dt.year == nat_y].groupby("country").value.sum()
     .drop("その他", errors="ignore").rename({"オーストラリア": "豪州"}))
w = w[w.index.isin(J.columns)] / w[w.index.isin(J.columns)].sum()
wg = (j_yoy[w.index] * w).sum(axis=1) / (j_yoy[w.index].notna() * w).sum(axis=1)  # 長野の客層で重みづけした全国の伸び
wg = wg[j_yoy["総数"].notna()]
ng = s.foreign / s.foreign.shift(12, freq="MS").reindex(s.index)
ev = data.events()
covid = ev[ev.kind == "covid"]
cv0, cv1 = covid.start.min().to_period("M").to_timestamp(), covid.end.max().to_period("M").to_timestamp()
both = pd.DataFrame({"wg": wg, "ng": ng}).dropna()
normal = both[[not (cv0 <= t <= cv1 or cv0 <= t - pd.DateOffset(years=1) <= cv1) for t in both.index]]
agree = ((normal.wg > 1) == (normal.ng > 1)).mean()
lead = (jl.year - last.year) * 12 + jl.month - last.month
jl_label = f"{jl.year}年{jl.month}月"
j_note = {"推計": "推計値", "暫定": "暫定値", "確定": "確定値"}[j_status[jl]]

ui.insight(
    f"{ym}の延べ宿泊者数は <b>{man(cur.guests, '人泊')}</b> で、前年同月より{updown(cur.guests / ly.guests - 1)}、"
    f"コロナ前（2019年{last.month}月）と比べると{updown(cur.guests / cv.guests - 1)}でした。"
    f"泊まった人のうち外国人は <b>{cur.foreign_share:.0%}</b>（前年同月 {ly.foreign_share:.0%}）です。"
    f"<br>年間で見ると、{iy}年の観光消費額は <b>{yen(spend)}</b> で前年より{updown(spend / spend_ly - 1)}"
    + (f"。県を訪れた人の数（実人数）は{updown(visitors / visitors_ly - 1)}なので、1人あたりの消費が伸びています。"
       if spend / spend_ly > visitors / visitors_ly + 0.02 else
       f"、県を訪れた人の数（実人数）は{updown(visitors / visitors_ly - 1)}でした。")
    + f"<br>一足早く分かる全国の訪日客（{jl_label}, {j_note}）は前年同月より"
      f"{updown(J.loc[jl, '総数'] / J.loc[jl - pd.DateOffset(years=1), '総数'] - 1)}。"
      f"長野県に泊まる外国人の国・地域の構成に合わせて見ると{updown(wg[jl] - 1)}"
    + ("で、県内の外国人宿泊も前年を下回る可能性があります。" if wg[jl] < 0.995 else
       "で、県内の外国人宿泊も前年を上回る可能性があります。" if wg[jl] > 1.005 else
       "で、県内の外国人宿泊も前年並みになりそうです。")
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

# ---- 訪日客はどこから ----
st.subheader("海外からのお客さまは、どの国・地域から？")
nat = data.shukuhaku_nationality()
ny = int(nat.ym.dt.year.max())
by = nat[nat.ym.dt.year == ny].groupby("country").value.sum()
base = nat[nat.ym.dt.year == 2019].groupby("country").value.sum()
named = by.drop("その他", errors="ignore").sort_values(ascending=False)
top = named.head(10)
rest = by.sum() - top.sum()
bars = pd.concat([top, pd.Series({"そのほか": rest})])
winter = nat[(nat.ym.dt.year == ny) & nat.ym.dt.month.isin([12, 1, 2])].groupby("country").value.sum()
winter = winter.drop("その他", errors="ignore").sort_values(ascending=False)
c1, c2 = st.columns([3, 2])
with c1:
    b = bars.iloc[::-1]
    chg = (b / base.reindex(b.index) - 1)
    fig = go.Figure(go.Bar(
        y=b.index, x=b.values / by.sum(), orientation="h",
        marker_color=[charts.CONTEXT if k == "そのほか" else charts.MAIN for k in b.index],
        text=[f"{v / by.sum():.0%}" for v in b.values], textposition="outside", cliponaxis=False,
        customdata=[[man(v, "人泊"), "" if pd.isna(c) else f"<br>2019年比 {c:+.0%}"] for v, c in zip(b.values, chg)],
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}（%{x:.1%}）%{customdata[1]}<extra></extra>",
    ))
    charts.layout(fig, height=360)
    fig.update_xaxes(tickformat=".0%", range=[0, b.max() / by.sum() * 1.2], showgrid=True,
                     gridcolor="rgba(128,128,128,.18)", title=f"{ny}年の外国人延べ宿泊者数に占める割合")
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)
with c2:
    grow = (named.head(10) / base.reindex(named.head(10).index) - 1).dropna().sort_values(ascending=False)
    st.markdown(
        f"- いちばん多いのは **{top.index[0]}**（{top.iloc[0] / by.sum():.0%}）、次いで{top.index[1]}・{top.index[2]}です。\n"
        f"- 冬（12〜2月）に限ると **{winter.index[0]}** と **{winter.index[1]}** が上位。スキーシーズンに合わせた来訪が多い国・地域です。\n"
        f"- コロナ前（2019年）と比べて大きく伸びたのは **{grow.index[0]}**（{grow.iloc[0]:+.0%}）と"
        f" **{grow.index[1]}**（{grow.iloc[1]:+.0%}）です。"
    )
    st.caption(f"出典: 観光庁「宿泊旅行統計調査」（{ny}年確定値, 参考第1表）。"
               "国籍別は従業者10人以上の施設の集計なので、上の外国人宿泊者数（全施設）より少し小さくなります。")


# ---- 全国の訪日客の動き（先行指標） ----
st.subheader("全国の訪日客の動き（先行指標）")
st.markdown(
    f"全国の訪日客数（JNTO）は、宿泊旅行統計より **{lead}か月早く** 公表されます。"
    f"長野県に泊まる外国人の国・地域の構成（{nat_y}年）に合わせて全国の伸びを計算すると、"
    f"コロナ期間を除く過去の月の **{agree:.0%}** で、県内の外国人宿泊と増減の向きがそろっていました。"
)
c1, c2 = st.columns([3, 2])
with c1:
    since = jl - pd.DateOffset(months=23)
    series = [("全国の訪日客（総数）", j_yoy["総数"], charts.CONTEXT, "dot"),
              ("全国の訪日客（長野の客層に合わせた伸び）", wg, charts.SECOND, "solid"),
              ("長野県の外国人延べ宿泊者", ng, charts.MAIN, "solid")]
    fig = go.Figure()
    for label, v, color, dash in series:
        v = (v[v.index >= since].dropna() - 1) * 100
        est = [j_status.get(t) == "推計" and "宿泊" not in label for t in v.index]
        fig.add_trace(go.Scatter(
            x=v.index, y=v.values, name=label, mode="lines+markers",
            line={"color": color, "width": 3 if "長野県" in label else 2, "dash": dash},
            marker={"size": 8, "symbol": ["circle-open" if e else "circle" for e in est]},
            hovertemplate=f"{label}<br>%{{x|%Y年%-m月}} 前年同月比 %{{y:+.0f}}%<extra></extra>",
        ))
    fig.add_hline(y=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
    charts.layout(fig, height=360, hovermode="x unified")
    fig.update_yaxes(title="前年同月比（%）", ticksuffix="%")
    fig.update_xaxes(tickformat="%Y年<br>%-m月", dtick="M3")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"白抜きの点は推計値。{last.year}年の宿泊の数字は速報値で、調査の区分けの見直しの影響を含むことがあります。"
               "出典: 日本政府観光局（JNTO）「訪日外客統計」、観光庁「宿泊旅行統計調査」")
with c2:
    top = w.sort_values(ascending=False).head(6)
    g3 = J.loc[jl - pd.DateOffset(months=2):jl, top.index].sum() / J.loc[
        jl - pd.DateOffset(months=14):jl - pd.DateOffset(months=12), top.index].sum() - 1
    b = g3.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=b.index, x=b.values, orientation="h",
        marker_color=[charts.MAIN if v >= 0 else charts.SECOND for v in b.values],
        text=[f"{v:+.0%}" for v in b.values], textposition="outside", cliponaxis=False,
        customdata=[f"{top[k]:.0%}" for k in b.index],
        hovertemplate="<b>%{y}</b><br>全国の訪日客 前年同期比 %{x:+.1%}<br>長野の外国人宿泊に占める割合 %{customdata}<extra></extra>",
    ))
    charts.layout(fig, height=300, title={"text": "長野の主なお客さまの国・地域（全国の直近3か月の伸び）", "font": {"size": 13}})
    lim = max(abs(b.values).max() * 1.35, 0.1)
    fig.update_xaxes(tickformat="+.0%", range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)
    up, down = g3.idxmax(), g3.idxmin()
    st.markdown(
        f"直近3か月（{(jl - pd.DateOffset(months=2)).month}〜{jl.month}月）、長野の主なお客さまのうち **{up}** は全国で"
        f" {g3[up]:+.0%}" + (f"、**{down}** は {g3[down]:+.0%} でした。" if g3[down] < 0 else "と、どの国・地域も前年を上回っています。")
    )

# ---- 長い目で見ると ----
with st.expander("長い目で見ると（2010年代からの宿泊者数と観光消費額）"):
    a = s[s.index.year < last.year].groupby(s.index.year[s.index.year < last.year])[["japanese", "foreign"]].sum()
    fig = go.Figure()
    for col, label, color in [("japanese", "日本人", charts.MAIN), ("foreign", "外国人", charts.SECOND)]:
        fig.add_trace(go.Bar(x=a.index, y=a[col] / 1e4, name=label, marker_color=color,
                             marker_line={"color": "white", "width": 1},
                             hovertemplate=f"%{{x}}年 {label} %{{y:,.0f}}万人泊<extra></extra>"))
    charts.layout(fig, height=300, barmode="stack", bargap=0.25, title={"text": "延べ宿泊者数", "font": {"size": 14}})
    fig.update_yaxes(title="万人泊")
    st.plotly_chart(fig, use_container_width=True)
    best = a.sum(axis=1).idxmax()
    normal = a.sum(axis=1).drop([2020, 2021, 2022], errors="ignore")
    st.markdown(
        f"コロナ禍（2020〜22年）を除くと、延べ宿泊者数は年 {man(normal.min(), '人泊')}〜{man(normal.max(), '人泊')} で推移し、"
        f"{best}年が最多でした。"
        f"外国人は {a.index[0]}年の {man(a.foreign.iloc[0], '人泊')} から {a.index[-1]}年には "
        f"{man(a.foreign.iloc[-1], '人泊')} に増え、全体の {a.foreign.iloc[-1] / a.sum(axis=1).iloc[-1]:.0%} になりました。"
    )

    sp_y = ann.spend.dropna()
    fig = go.Figure(go.Bar(x=sp_y.index, y=sp_y.values / 1e8, marker_color=charts.MAIN,
                           hovertemplate="%{x}年 %{y:,.0f}億円<extra></extra>"))
    charts.layout(fig, height=280, bargap=0.25, title={"text": "観光消費額（県全体）", "font": {"size": 14}})
    fig.update_yaxes(title="億円")
    st.plotly_chart(fig, use_container_width=True)
    first = sp_y.index.min()
    st.markdown(
        f"観光消費額は {first}年の {yen(sp_y.iloc[0])} から {iy}年の {yen(sp_y.iloc[-1])} へ、"
        f"約 {sp_y.iloc[-1] / sp_y.iloc[0]:.1f} 倍になりました。"
        + (f"県を訪れた人の数（実人数）は同じ期間に {ann.visitors[iy] / ann.visitors[first]:.2f} 倍とほぼ横ばいなので、"
           "**1人あたりの消費額が上がったこと**が伸びの中心です。"
           if abs(ann.visitors[iy] / ann.visitors[first] - 1) < 0.15 else "")
    )
    st.caption("出典: 観光庁「宿泊旅行統計調査」、長野県「観光入込客統計」（観光庁 共通基準）。"
               "入込客統計の2010〜2015年はビジネス目的、2017・2018年は入込客数が「参考値」とされています。")

ui.sources(["boundaries", "shukuhaku", "irikomi", "riyousha", "jnto"])

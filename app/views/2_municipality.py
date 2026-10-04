import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, maps, ui
from lib.charts import man, updown, yen

ui.setup("市町村を深掘りする", "ひとつの市町村を選んで、エリアごとの特徴と季節の動きを見るページです。", kicker="市町村")

g = data.municipalities()
names = g.sort_values("code").name.tolist()
name = st.selectbox("市町村を選んでください", names, index=names.index("長野市"))
row = g[g.name == name].iloc[0]

sp = data.riyousha_spots()
ry = int(sp.year.max())
mine = sp[sp.municipality_code == row.code]
now, before = mine[mine.year == ry], mine[mine.year == ry - 1].set_index("spot")
if now.empty:
    ui.insight(f"{name}は{row.kouiki}広域（{row.chiiki}）に属します。"
               f"県の観光地利用者統計調査（{ry}年）には、{name}の観光地は入っていません。")
else:
    tot, tot_ly = now.total.sum(), before.total.sum()
    pre = mine[mine.year == 2019].total.sum()
    now = now.assign(ly=now.spot.map(before.total))
    now["chg"] = (now.total / now.ly - 1).where(now.ly > 0)  # 新規の観光地は前年比なし
    grow = now[(now.ly > 0) & (now.total >= 10_000)].sort_values("chg")
    monthly = now[charts.MONTHS].sum()
    text = (f"{name}の観光地（{len(now)}か所）には、{ry}年に延べ <b>{man(tot)}</b> が訪れ、"
            + (f"前年より{updown(tot / tot_ly - 1)}でした" if tot_ly > 0 else "でした")
            + f"（観光地での消費額 {yen(now.spend.sum())}）。"
            + (f"コロナ前（2019年）と比べると{updown(tot / pre - 1)}です。" if pre > 0 else "")
            + f"いちばん多いのは <b>{now.sort_values('total').spot.iloc[-1]}</b>、"
            f"季節のピークは <b>{int(monthly.idxmax()[1:])}月</b> です。")
    if len(grow) >= 2 and grow.chg.iloc[-1] > 0.02:
        text += f"<br>伸びが大きいのは {grow.spot.iloc[-1]}（{grow.chg.iloc[-1]:+.0%}）"
        text += (f"、落ち込みが大きいのは {grow.spot.iloc[0]}（{grow.chg.iloc[0]:+.0%}）です。"
                 if grow.chg.iloc[0] < -0.02 else "です。")
    ui.insight(text)

left, right = st.columns([3, 2])
with left:
    st.plotly_chart(
        maps.municipality_map(g, highlight={row.code}, focus=g[g.code == row.code], height=480),
        use_container_width=True,
    )
    st.caption(maps.ATTRIBUTION)
with right:
    st.subheader("市町村内のエリア")
    areas = data.sub_areas()
    areas = areas[areas.municipality_code == row.code]
    if areas.empty:
        st.info("この市町村のエリア分けはまだ定義していません。観光地ごとの集計から作れます。")
    else:
        for a in areas.itertuples():
            st.markdown(f"- **{a.area_name}** … {a.definition}")
        st.caption("エリアの境界は、国勢調査の小地域（町丁・字）を組み合わせて正確に作る予定です。")

if not now.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("観光地ランキング")
        top = now.sort_values("total", ascending=False).head(12).iloc[::-1]
        fig = go.Figure(go.Bar(
            y=top.spot, x=top.total / 1e4, orientation="h", marker_color=charts.MAIN,
            text=[man(v) for v in top.total], textposition="outside", cliponaxis=False,
            customdata=top[["chg", "category"]].values,
            hovertemplate="<b>%{y}</b>（%{customdata[1]}）<br>延べ %{x:,.1f}万人"
                          "<br>前年比 %{customdata[0]:+.1%}<extra></extra>",
        ))
        charts.layout(fig, height=max(260, 34 * len(top) + 60))
        fig.update_xaxes(title=f"{ry}年の延べ利用者数（万人）", showgrid=True,
                         gridcolor="rgba(128,128,128,.18)", range=[0, top.total.max() / 1e4 * 1.25])
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(fig, use_container_width=True)
        if len(now) > len(top):
            st.caption(f"上位{len(top)}か所を表示（全{len(now)}か所）。")
    with c2:
        st.subheader("季節ごとの来訪")
        fig = go.Figure()
        for y, color, width, dash in [(2019, charts.CONTEXT, 2, "dot"), (ry - 1, charts.CONTEXT, 2, "solid"),
                                      (ry, charts.MAIN, 3, "solid")]:
            if not (mine.year == y).any():
                continue
            m = mine[mine.year == y][charts.MONTHS].sum()
            fig.add_trace(go.Scatter(
                x=list(range(1, 13)), y=m.values / 1e4, name=f"{y}年" + ("（コロナ前）" if y == 2019 else ""),
                mode="lines+markers", line={"color": color, "width": width, "dash": dash}, marker={"size": 7},
                hovertemplate=f"{y}年 %{{x}}月<br>%{{y:,.1f}}万人<extra></extra>",
            ))
        charts.layout(fig, height=360, hovermode="x unified")
        fig.update_xaxes(tickvals=list(range(1, 13)), ticktext=[f"{m}月" for m in range(1, 13)])
        fig.update_yaxes(title="延べ利用者数（万人）", rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True)
        day = now.higaeri.sum() / now.total.sum()
        out = now.kengai.sum() / now.total.sum()
        st.markdown(f"訪れた人の **{out:.0%}** が県外から、**{day:.0%}** が日帰りです。")
    st.caption(f"出典: 長野県「観光地利用者統計調査」。延べ利用者数は日帰り客と宿泊客の延べ人数の合計です。")

    hist = data.riyousha_history()
    hist = hist[hist.municipality_code == row.code]
    with st.expander(f"長い目で見ると（{hist.year.min()}年からの延べ利用者数）"):
        yearly = hist.groupby("year").visitors.sum()
        fig = go.Figure(go.Bar(x=yearly.index, y=yearly.values / 1e4, marker_color=charts.MAIN,
                               hovertemplate="%{x}年 %{y:,.1f}万人<extra></extra>"))
        charts.layout(fig, height=300, bargap=0.25)
        fig.update_yaxes(title="延べ利用者数（万人）")
        st.plotly_chart(fig, use_container_width=True)
        top_spots = now.sort_values("total", ascending=False).spot.head(5)
        trend = hist[hist.spot.isin(top_spots)].pivot_table(index="year", columns="spot", values="visitors")
        first = trend.apply(lambda c: c.first_valid_index())
        chg = {sp: trend[sp].iloc[-1] / trend[sp][first[sp]] - 1 for sp in trend.columns if trend[sp][first[sp]] > 0}
        st.markdown(
            f"{yearly.index[0]}年の {man(yearly.iloc[0])} に対して、{yearly.index[-1]}年は {man(yearly.iloc[-1])}"
            f"（{updown(yearly.iloc[-1] / yearly.iloc[0] - 1)}）。"
            + "上位の観光地では、" + "、".join(f"{sp} {c:+.0%}" for sp, c in sorted(chg.items(), key=lambda x: -x[1]))
            + f"（{yearly.index[0]}年比、調査開始が遅い観光地はその年から）。"
        )
        st.caption("観光地の追加・統合があるため、年による増減には調査対象の変化も含まれます。")

    with st.expander("観光地ごとの数字（表）"):
        tbl = now.sort_values("total", ascending=False)[["spot", "category", "total", "chg", "kengai", "shukuhaku", "spend"]]
        tbl = tbl.assign(kengai=tbl.kengai / tbl.total, shukuhaku=tbl.shukuhaku / tbl.total)
        st.dataframe(
            tbl, hide_index=True, use_container_width=True,
            column_config={
                "spot": "観光地", "category": "類型",
                "total": st.column_config.NumberColumn(f"延べ利用者数（{ry}年）", format="%,d 人"),
                "chg": st.column_config.NumberColumn("前年比", format="percent"),
                "kengai": st.column_config.NumberColumn("県外客の割合", format="percent"),
                "shukuhaku": st.column_config.NumberColumn("宿泊客の割合", format="percent"),
                "spend": st.column_config.NumberColumn("観光地消費額", format="%,d 円"),
            },
        )

ui.sources(["boundaries", "riyousha", "digital", "kokusei_area"])

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, maps, muni, ui
from lib.charts import man

ui.setup("県内のどこへ？", "市町村・広域・観光地・エリアごとの人の集まり方。")

sp = data.riyousha_spots()
ry = int(sp.year.max())
cur, prev, y19 = sp[sp.year == ry], sp[sp.year == ry - 1], sp[sp.year == 2019]
g = data.municipalities()
muni_m = g.set_index("code")
names = muni_m.name
vt = muni.vtable()
ly, Y, SPAN = vt.attrs["year"], vt.attrs["Y"], vt.attrs["span"]
vis = vt.visitors.dropna().sort_values(ascending=False)
kk = vt.groupby("kouiki").visitors.sum().sort_values(ascending=False)
SRC_D = "日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成"

ui.insight(
    f"{ly}年に県内の市町村を観光で訪れた人は、<b>{names[vis.index[0]]}・{names[vis.index[1]]}・{names[vis.index[2]]}</b> が多く、"
    f"この3市町で市町村の合計の {vis.iloc[:3].sum() / vis.sum():.0%} を占めます。"
    f"広域では <b>{kk.index[0]}</b> がいちばん多く（{kk.iloc[0] / kk.sum():.0%}）なっています。"
)

# ---- 1. 市町村ランキング ----
with ui.card():
    ui.block("市町村別の観光来訪者数", f"{ly}年の上位20市町村。（ ）内は住民1人あたり")
    top20 = vis.head(20).iloc[::-1]
    pr = vt.per_resident
    fig = go.Figure(go.Bar(
        y=[names[c] for c in top20.index], x=top20 / 1e4, orientation="h", marker_color=charts.MAIN,
        text=[f"{v / 1e4:,.0f}万人（{pr[c]:,.0f}人）" for c, v in top20.items()],
        textposition="outside", cliponaxis=False, hovertemplate="%{y} %{x:,.1f}万人<extra></extra>",
    ))
    charts.layout(fig, height=620)
    fig.update_xaxes(title="観光来訪者数（万人）", range=[0, top20.max() / 1e4 * 1.4])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    hi = vt.dropna(subset=["per_resident"]).sort_values("per_resident", ascending=False)
    ui.readout([
        f"上位3市町（{'・'.join(names[c] for c in vis.index[:3])}）で市町村の合計の {vis.iloc[:3].sum() / vis.sum():.0%}、"
        f"上位20市町村で {vis.head(20).sum() / vis.sum():.0%} を占めます。",
        f"住民1人あたりの来訪者がいちばん多いのは **{hi.name.iloc[0]}**（{hi.per_resident.iloc[0]:,.0f}人）、次いで {hi.name.iloc[1]}（{hi.per_resident.iloc[1]:,.0f}人）です。",
        "市町村をまたいで回った人は、それぞれの市町村で1人と数えます（市町村の合計は県全体の人数より多くなります）。",
    ], source=f"{SRC_D}（{ly}年）、総務省「国勢調査」（2020年）")
    with st.expander("地図で見る"):
        st.plotly_chart(maps.municipality_map(g, outlines=data.kouiki(), values=vis.to_dict(),
                                              value_label=f"{ly}年の観光来訪者数", fmt=man, missing="公表なし（人数が少ない月がある）"),
                        use_container_width=True)
        st.caption(maps.ATTRIBUTION)

# ---- 2. 観光地ランキング ----
with ui.card():
    ui.block("観光地ランキング", "延べ利用者数の上位15か所と前年比")
    t = cur.set_index("spot")
    t = t.assign(ly=t.index.map(prev.set_index("spot").total.groupby(level=0).sum()))
    top = t.nlargest(15, "total").iloc[::-1]
    chg = top.total / top.ly - 1
    fig = go.Figure(go.Bar(
        y=[f"{s}（{m}）" for s, m in zip(top.index, top.municipality)], x=top.total / 1e4, orientation="h", marker_color=charts.MAIN,
        text=[f"{v / 1e4:,.0f}万人" + ("" if pd.isna(c) else f"（{c:+.0%}）") for v, c in zip(top.total, chg)],
        textposition="outside", cliponaxis=False, hovertemplate="%{y} %{x:,.1f}万人<extra></extra>",
    ))
    charts.layout(fig, height=520)
    fig.update_xaxes(title="延べ利用者数（万人）", range=[0, top.total.max() / 1e4 * 1.3])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    big = t[(t.total >= 100_000) & (t.ly > 0)].assign(chg=lambda x: x.total / x.ly - 1).sort_values("chg")
    ui.readout([
        f"いちばん多いのは **{top.index[-1]}**（{top.municipality.iloc[-1]}, {man(top.total.iloc[-1])}）です。",
        f"トップ15で、県の調査対象の観光地（{len(cur)}か所）の合計の {top.total.sum() / cur.total.sum():.0%} を占めます。",
        f"10万人以上の観光地のうち、前年から大きく伸びたのは **{big.index[-1]}**（{big.chg.iloc[-1]:+.0%}）、"
        + (f"大きく減ったのは **{big.index[0]}**（{big.chg.iloc[0]:+.0%}）です。" if big.chg.iloc[0] < 0 else "どれも前年を上回りました。")
        if len(big) >= 2 else "",
    ], source=f"長野県「観光地利用者統計調査」（{ry}年）。（ ）内は前年比")

# ---- 3. 10広域 ----
with ui.card():
    ui.block("広域別の観光来訪者数", f"{ly}年。市町村の合計と、住民1人あたり")
    pop = muni.population()
    kp = kk / pop.reindex(vt.index)[vt.visitors.notna()].groupby(vt.kouiki).sum().reindex(kk.index)
    c1, c2 = st.columns(2)
    with c1:
        b = kk.iloc[::-1]
        fig = go.Figure(go.Bar(y=[f"{k}広域" for k in b.index], x=b / 1e4, orientation="h", marker_color=charts.MAIN,
                               text=[man(v) for v in b], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} %{x:,.1f}万人<extra></extra>"))
        charts.layout(fig, height=380, title={"text": "観光来訪者数（市町村の合計）", "font": {"size": 14}})
        fig.update_xaxes(range=[0, b.max() / 1e4 * 1.35])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    with c2:
        b = kp.sort_values()
        fig = go.Figure(go.Bar(y=[f"{k}広域" for k in b.index], x=b, orientation="h", marker_color=charts.MAIN,
                               text=[f"{v:,.0f}人" for v in b], textposition="outside", cliponaxis=False,
                               hovertemplate="%{y} 住民1人あたり %{x:,.0f}人<extra></extra>"))
        charts.layout(fig, height=380, title={"text": "住民1人あたりの来訪者", "font": {"size": 14}})
        fig.update_xaxes(range=[0, b.max() * 1.35])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig)
    ui.readout([
        f"人数がいちばん多いのは **{kk.index[0]}広域**（{man(kk.iloc[0])}）、少ないのは **{kk.index[-1]}広域**（{man(kk.iloc[-1])}）です。",
        f"住民1人あたりでは **{kp.idxmax()}広域**（{kp.max():,.0f}人）がいちばん多く、住民の数に比べて観光の比重が大きい地域です。",
    ], source=f"{SRC_D}（{ly}年）、総務省「国勢調査」（2020年）。人数が少なく公表されていない月がある市町村は含みません")
    st.page_link("views/kouiki/0_top.py", label="広域ごとに詳しく見る →")

# ---- 4. 県内5エリアの宿泊 ----
with ui.card():
    ui.block("県内5エリアの延べ宿泊者数", "最新年と前年比")
    ar = data.shukuhaku_area()
    ar["area"] = ar.area.str.replace("長野県", "")
    cnt = ar.groupby(ar.ym.dt.year).ym.nunique()
    yrs = cnt[cnt == 12 * ar.area.nunique() // ar.area.nunique()].index
    ay = ar[ar.ym.dt.year.isin(yrs)].groupby([ar.ym.dt.year, "area"]).guests.sum().unstack()
    order = ay.iloc[-1].sort_values(ascending=False).index
    yoy_a = ay.iloc[-1] / ay.iloc[-2] - 1
    b = ay.iloc[-1].reindex(order[::-1])
    fig = go.Figure(go.Bar(
        y=b.index, x=b / 1e4, orientation="h", marker_color=charts.MAIN,
        text=[f"{v / 1e4:,.0f}万人泊（前年比 {yoy_a[k]:+.0%}）" for k, v in b.items()], textposition="outside", cliponaxis=False,
        hovertemplate="%{y} %{x:,.0f}万人泊<extra></extra>",
    ))
    charts.layout(fig, height=280, title={"text": f"{ay.index[-1]}年の延べ宿泊者数", "font": {"size": 14}})
    fig.update_xaxes(title="万人泊", range=[0, b.max() / 1e4 * 1.5])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    g2 = (ay.iloc[-1] / ay.iloc[-2] - 1).sort_values()
    ui.readout([
        f"{ay.index[-1]}年にいちばん泊まった人が多いのは **{order[0]}** エリア（県全体の {ay.iloc[-1][order[0]] / ay.iloc[-1].sum():.0%}）です。",
        f"前年からの伸びが大きいのは **{g2.index[-1]}**（{g2.iloc[-1]:+.0%}）、小さいのは **{g2.index[0]}**（{g2.iloc[0]:+.0%}）です。",
    ], source="観光庁「宿泊旅行統計調査」広域市町村（130区分）別参考表")
    with st.expander("5エリアに入る市町村"):
        st.dataframe(data.shukuhaku_area_map(), hide_index=True, use_container_width=True)

# ---- 5. 観光地の種類 ----
with ui.card():
    ui.block("観光地の種類別の利用者数", "2019年との比較")
    c = pd.DataFrame({"2019年": y19.groupby("category").total.sum(), f"{ry}年": cur.groupby("category").total.sum()})
    fig = go.Figure()
    for col, color in [("2019年", charts.CONTEXT), (f"{ry}年", charts.MAIN)]:
        fig.add_trace(go.Bar(x=c.index, y=c[col] / 1e4, name=col, marker_color=color, marker_line={"color": "white", "width": 2},
                             hovertemplate=f"%{{x}} {col} %{{y:,.0f}}万人<extra></extra>"))
    charts.layout(fig, height=300, barmode="group", bargap=0.3)
    fig.update_yaxes(title="延べ利用者数（万人）")
    ui.chart(fig)
    cc = (c[f"{ry}年"] / c["2019年"] - 1).sort_values()
    ui.readout([
        f"いちばん多いのは **{c[f'{ry}年'].idxmax()}**（全体の {c[f'{ry}年'].max() / c[f'{ry}年'].sum():.0%}）です。",
        "2019年からの増減: " + "、".join(f"{k} {v:+.0%}" for k, v in cc.items()) + "。",
    ], source="長野県「観光地利用者統計調査」")

    c1, c2 = st.columns(2)
    with c1:
        st.page_link("views/muni/0_top.py", label="市町村を選んで詳しく見る →")
    with c2:
        st.page_link("views/kouiki/0_top.py", label="広域で連携する（広域ごとに見る）→")

ui.sources(["digital", "riyousha", "shukuhaku", "population", "boundaries"])

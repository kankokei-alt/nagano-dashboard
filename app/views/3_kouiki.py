import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, maps, ui
from lib.charts import man, updown

ui.setup("広域で連携する", "複数の市町村をまとめて、ひとつの観光圏として見るページです。", kicker="広域連携")

g = data.municipalities()
k = data.kouiki()
mode = st.radio("まとめ方", ["10広域から選ぶ", "市町村を自由に選ぶ"], horizontal=True)
if mode == "10広域から選ぶ":
    region = st.selectbox("広域", sorted(g.kouiki.unique()), index=sorted(g.kouiki.unique()).index("北アルプス"))
    selected = g[g.kouiki == region]
else:
    picks = st.multiselect("市町村（2つ以上）", g.sort_values("code").name.tolist(),
                           default=["白馬村", "小谷村", "大町市"])
    selected = g[g.name.isin(picks)]

if selected.empty:
    st.warning("市町村を選んでください。")
    st.stop()

sp = data.riyousha_spots()
ry = int(sp.year.max())
area = sp[sp.municipality_code.isin(selected.code)]
now = area[area.year == ry]
by_muni = now.groupby("municipality").total.sum().sort_values(ascending=False)
missing = sorted(set(selected.name) - set(by_muni.index))

if now.empty:
    ui.insight(f"選んだ市町村には、県の観光地利用者統計調査（{ry}年）の対象の観光地がありません。")
else:
    tot, tot_ly = now.total.sum(), area[area.year == ry - 1].total.sum()
    monthly = now[charts.MONTHS].sum()
    mshare = monthly / monthly.sum()
    peak, low = int(mshare.idxmax()[1:]), int(mshare.idxmin()[1:])
    text = (f"選んだ圏域の観光地には、{ry}年に延べ <b>{man(tot)}</b> が訪れました"
            + (f"（前年より{updown(tot / tot_ly - 1)}）。" if tot_ly > 0 else "。"))
    if len(by_muni) >= 2 and by_muni.iloc[0] / tot >= 0.5:
        text += f"そのうち <b>{by_muni.index[0]}</b> が {by_muni.iloc[0] / tot:.0%} を占め、来訪が集中しています。"
    elif len(by_muni) >= 3:
        text += (f"<b>{by_muni.index[0]}</b>と<b>{by_muni.index[1]}</b>の2つで "
                 f"{by_muni.iloc[:2].sum() / tot:.0%} を占めます。")
    text += (f"<br>圏域全体のピークは <b>{peak}月</b>（年間の {mshare.max():.0%}）、"
             f"いちばん少ないのは <b>{low}月</b>（{mshare.min():.0%}）です。"
             "ピークの重ならない市町村どうしの周遊や、少ない月の企画に連携の余地があります。")
    ui.insight(text)
st.plotly_chart(
    maps.municipality_map(g, highlight=set(selected.code), outlines=k, focus=selected, height=520),
    use_container_width=True,
)
st.caption(maps.ATTRIBUTION)

if not now.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("圏域内のシェア")
        b = by_muni.iloc[::-1]
        fig = go.Figure(go.Bar(
            y=b.index, x=b.values / tot, orientation="h", marker_color=charts.MAIN,
            text=[f"{v / tot:.0%}（{man(v)}）" for v in b.values], textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>圏域の %{x:.1%}<extra></extra>",
        ))
        charts.layout(fig, height=max(240, 38 * len(b) + 60))
        fig.update_xaxes(tickformat=".0%", range=[0, b.max() / tot * 1.45], showgrid=True,
                         gridcolor="rgba(128,128,128,.18)", title=f"{ry}年の延べ利用者数に占める割合")
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("季節のかぶり・すき間")
        hm = now.groupby("municipality")[charts.MONTHS].sum()
        hm = hm.div(hm.sum(axis=1), axis=0).reindex(by_muni.index)
        fig = go.Figure(go.Heatmap(
            z=hm.values, x=[f"{m}月" for m in range(1, 13)], y=hm.index,
            colorscale=[[i / (len(charts.SEQ) - 1), c] for i, c in enumerate(charts.SEQ)],
            xgap=2, ygap=2, colorbar={"title": "年間に<br>占める割合", "tickformat": ".0%"},
            hovertemplate="<b>%{y}</b> %{x}<br>年間の %{z:.1%}<extra></extra>",
        ))
        charts.layout(fig, height=max(240, 38 * len(hm) + 60))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        st.plotly_chart(fig, use_container_width=True)
        peaks = hm.idxmax(axis=1).str[1:].astype(int)
        same = (peaks == peaks.mode().iloc[0]).sum()
        st.markdown(f"色が濃いほど、その月に来訪が集中しています。{len(hm)}市町村のうち **{same}** が "
                    f"**{peaks.mode().iloc[0]}月** にピークを迎えます。")
    st.caption(f"出典: 長野県「観光地利用者統計調査」（{ry}年）。延べ利用者数は日帰り客と宿泊客の延べ人数の合計です。"
               + (f" {'・'.join(missing)}は調査対象の観光地がないため含みません。" if missing else ""))

# ---- 宿泊で見ると（観光庁の県内5エリア） ----
amap = data.shukuhaku_area_map()
hit = amap[amap.municipality_code.isin(selected.code)].area.value_counts()
if not hit.empty:
    st.subheader("宿泊で見ると")
    area = hit.index[0]
    if len(hit) > 1:
        area = st.radio("観光庁の集計エリア（選んだ市町村を含むもの）", list(hit.index), horizontal=True,
                        format_func=lambda a: amap[amap.area == a].area_full.iloc[0].removeprefix("長野県"))
    members = amap[amap.area == area]
    sa = data.shukuhaku_area()
    sa = sa[sa.area == area]
    yr = sa.groupby(sa.ym.dt.year)[["guests", "foreign"]].sum()
    full = yr.index.max()
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure()
        for col, label, color in [("japanese", "日本人", charts.MAIN), ("foreign", "外国人", charts.SECOND)]:
            v = yr.guests - yr.foreign if col == "japanese" else yr.foreign
            fig.add_trace(go.Bar(x=yr.index, y=v / 1e4, name=label, marker_color=color,
                                 marker_line={"color": "white", "width": 1},
                                 hovertemplate=f"%{{x}}年 {label} %{{y:,.0f}}万人泊<extra></extra>"))
        charts.layout(fig, height=300, barmode="stack", bargap=0.3, legend_traceorder="normal")
        fig.update_yaxes(title="延べ宿泊者数（万人泊）")
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        m = sa[sa.ym.dt.year == full].set_index(sa[sa.ym.dt.year == full].ym.dt.month)
        st.markdown(
            f"**{members.area_full.iloc[0].removeprefix('長野県')}** エリア（{len(members)}市町村）の延べ宿泊者数は、"
            f"{full}年に **{man(yr.guests[full], '人泊')}**"
            + (f"（前年より{updown(yr.guests[full] / yr.guests[full - 1] - 1)}）" if full - 1 in yr.index else "")
            + f"。外国人の割合は **{yr.foreign[full] / yr.guests[full]:.0%}** で、"
            f"いちばん多いのは {m.guests.idxmax()}月、外国人は {m.foreign.idxmax()}月に集中します。"
        )
        st.caption("このエリアに含まれる市町村: " + "・".join(members.municipality))
    st.caption("出典: 観光庁「宿泊旅行統計調査」参考表（広域市町村130区分別, 確定値）。"
               "観光庁の集計エリアは県の10広域とは範囲が違います。")

ui.sources(["boundaries", "riyousha", "shukuhaku", "digital"])

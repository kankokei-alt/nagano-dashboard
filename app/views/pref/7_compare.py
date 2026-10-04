import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui
from lib.charts import man

ui.setup("他の県と比べる", "全国の中での長野県の位置。")

a = data.shukuhaku_all()
a = a[a.pref_code != "00"]
w = a.pivot_table(index=["pref_name", "ym"], columns="metric", values="value")
last = a.ym.max()
win = (w.index.get_level_values("ym") > last - pd.DateOffset(months=12))
win19 = w.index.get_level_values("ym").isin(pd.date_range(last.replace(year=2019) - pd.DateOffset(months=11), last.replace(year=2019), freq="MS"))
cur = w[win].groupby(level=0)[["guests", "foreign"]].sum()
cur["occupancy"] = w[win].groupby(level=0).occupancy.mean()
cur["foreign_share"] = cur.foreign / cur.guests
cur["vs2019"] = cur.guests / w[win19].groupby(level=0).guests.sum() - 1
cur["foreign_vs2019"] = cur.foreign / w[win19].groupby(level=0).foreign.sum() - 1
rank = cur.rank(ascending=False)
N = "長野県"
period = f"{(last - pd.DateOffset(months=11)).year}年{(last - pd.DateOffset(months=11)).month}月〜{last.year}年{last.month}月"

ui.insight(
    f"直近12か月（{period}）の延べ宿泊者数で、長野県は <b>全国{int(rank.loc[N, 'guests'])}位</b>（{man(cur.loc[N, 'guests'], '人泊')}）。"
    f"コロナ前（2019年の同じ期間）からの伸びは {cur.loc[N, 'vs2019']:+.0%} で全国{int(rank.loc[N, 'vs2019'])}位、"
    f"外国人の割合は {cur.loc[N, 'foreign_share']:.0%} で{int(rank.loc[N, 'foreign_share'])}位、"
    f"客室稼働率は {cur.loc[N, 'occupancy']:.0f}% で{int(rank.loc[N, 'occupancy'])}位です。"
    f"<br>インバウンドに絞ると、外国人延べ宿泊者数は <b>全国{int(rank.loc[N, 'foreign'])}位</b>（{man(cur.loc[N, 'foreign'], '人泊')}）、"
    f"2019年からの伸びは {cur.loc[N, 'foreign_vs2019']:+.0%} で{int(rank.loc[N, 'foreign_vs2019'])}位です。"
)

# ---- 1. ランキング ----
with ui.card():
    ui.block("延べ宿泊者数の都道府県順位", "直近12か月、上位20")
    top = cur.guests.sort_values(ascending=False)
    show = top.head(20)
    if N not in show.index:
        show = pd.concat([show, top[[N]]])
    show = show.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=show.index, x=show / 1e4, orientation="h",
        marker_color=[charts.MAIN if k == N else charts.CONTEXT for k in show.index],
        text=[f"{v / 1e4:,.0f}万" for v in show], textposition="outside", cliponaxis=False,
        hovertemplate="%{y} %{x:,.0f}万人泊<extra></extra>",
    ))
    charts.layout(fig, height=560)
    fig.update_xaxes(title="延べ宿泊者数（万人泊）", range=[0, show.max() / 1e4 * 1.15])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    near = top.index.get_loc(N)
    ui.readout([
        f"長野県は **{near + 1}位**。すぐ上は {top.index[near - 1]}（{man(top.iloc[near - 1], '人泊')}）、すぐ下は {top.index[near + 1]}（{man(top.iloc[near + 1], '人泊')}）です。",
        f"1位の{top.index[0]}は長野県の約 {top.iloc[0] / top[N]:.1f} 倍です。",
    ], source="観光庁「宿泊旅行統計調査」" + ("（今年は速報値）" if last.year >= 2026 else ""))

# ---- 2. インバウンドの全国順位 ----
with ui.card():
    ui.block("インバウンドの全国順位", "外国人延べ宿泊者数（直近12か月）、上位20と長野県")
    cols = st.columns(3)
    for c, (key, label, fmt) in zip(cols, [("foreign", "外国人延べ宿泊者数", lambda v: man(v, "人泊")),
                                           ("foreign_share", "宿泊者に占める外国人の割合", lambda v: f"{v:.1%}"),
                                           ("foreign_vs2019", "外国人宿泊の2019年比", lambda v: f"{v:+.0%}")]):
        with c:
            ui.kpi(label, f"全国{int(rank.loc[N, key])}位", f"長野県 {fmt(cur.loc[N, key])}／全国の中央値 {fmt(cur[key].median())}")
    ft = cur.foreign.sort_values(ascending=False)
    show = ft.head(20)
    if N not in show.index:
        show = pd.concat([show, ft[[N]]])
    show = show.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=show.index, x=show / 1e4, orientation="h",
        marker_color=[charts.MAIN if k == N else charts.CONTEXT for k in show.index],
        text=[f"{v / 1e4:,.0f}万（{cur.loc[k, 'foreign_share']:.0%}）" for k, v in show.items()], textposition="outside", cliponaxis=False,
        hovertemplate="%{y} %{x:,.1f}万人泊<extra></extra>",
    ))
    charts.layout(fig, height=560)
    fig.update_xaxes(title="外国人延べ宿泊者数（万人泊）", range=[0, show.max() / 1e4 * 1.25])
    fig.update_yaxes(showgrid=False)
    ui.chart(fig)
    fn = ft.index.get_loc(N)
    non_metro = ft.drop(["東京都", "大阪府", "京都府", "北海道", "沖縄県", "千葉県", "福岡県", "愛知県", "神奈川県"], errors="ignore")
    ui.readout([
        f"長野県の外国人延べ宿泊者数は **全国{fn + 1}位**。すぐ上は {ft.index[fn - 1]}、すぐ下は {ft.index[fn + 1]} です。",
        f"三大都市圏・北海道・沖縄・福岡を除くと **{list(non_metro.index).index(N) + 1}位** です。",
        f"宿泊者に占める外国人の割合は {cur.loc[N, 'foreign_share']:.1%}（全国{int(rank.loc[N, 'foreign_share'])}位）、"
        f"2019年からの伸びは {cur.loc[N, 'foreign_vs2019']:+.0%}（全国{int(rank.loc[N, 'foreign_vs2019'])}位）です。",
    ], source="観光庁「宿泊旅行統計調査」。棒の（ ）内は宿泊者に占める外国人の割合")

# ---- 3. 散布図 ----
with ui.card():
    ui.block("回復と外国人比率の位置", "横：2019年比の伸び、縦：外国人比率、円の大きさ：延べ宿泊者数")
    LABEL = {N, "北海道", "東京都", "京都府", "大阪府", "沖縄県", "新潟県", "山梨県", "岐阜県", "群馬県", "静岡県", "石川県"}
    fig = go.Figure()
    for is_n in (False, True):
        p = cur[(cur.index == N) == is_n]
        fig.add_trace(go.Scatter(
            x=p.vs2019, y=p.foreign_share, mode="markers+text", text=[k if k in LABEL else "" for k in p.index],
            textposition="top center", textfont={"size": 13 if is_n else 11},
            marker={"size": (p.guests / cur.guests.max()) ** 0.5 * 50 + 6, "color": charts.MAIN if is_n else charts.CONTEXT,
                    "opacity": 1 if is_n else 0.65, "line": {"color": "white", "width": 2}},
            customdata=list(zip(p.index, p.guests / 1e4)), showlegend=False,
            hovertemplate="%{customdata[0]}<br>2019年比 %{x:+.0%}<br>外国人の割合 %{y:.0%}<br>%{customdata[1]:,.0f}万人泊<extra></extra>",
        ))
    fig.add_vline(x=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
    charts.layout(fig, height=480)
    fig.update_xaxes(title="延べ宿泊者数 2019年の同じ期間からの伸び", tickformat="+.0%")
    fig.update_yaxes(title="外国人の割合", tickformat=".0%")
    ui.chart(fig)
    med_g, med_f = cur.vs2019.median(), cur.foreign_share.median()
    ui.readout([
        f"47都道府県の真ん中（中央値）は、伸び {med_g:+.0%}・外国人の割合 {med_f:.0%} です。",
        f"長野県は伸びが{'真ん中より大きく' if cur.loc[N, 'vs2019'] > med_g else '真ん中より小さく'}、"
        f"外国人の割合は{'真ん中より高い' if cur.loc[N, 'foreign_share'] > med_f else '真ん中より低い'}位置にいます。",
    ], source="観光庁「宿泊旅行統計調査」")

# ---- 3. 似た県と比べる ----
with ui.card():
    ui.block("類似県との比較", "延べ宿泊者数（直近12か月合計）、2019年＝100")
    prefs = sorted(cur.index, key=lambda k: a[a.pref_name == k].pref_code.iloc[0])
    peers = st.multiselect("比べる県", [p for p in prefs if p != N], default=["新潟県", "群馬県", "山梨県", "岐阜県", "北海道"])
    g = w.guests.unstack(0).sort_index()
    r12 = g.rolling(12).sum()
    idx = r12.div(r12.loc[pd.Timestamp(2019, 12, 1)]) * 100  # 2019年1〜12月の合計＝100
    idx = idx[idx.index >= pd.Timestamp(2019, 12, 1)]
    fig = go.Figure()
    ends = charts.spread({k: idx[k].dropna().iloc[-1] for k in peers + [N]}, gap=(idx[peers + [N]].max().max() - idx[peers + [N]].min().min()) * 0.05)
    for k in peers + [N]:
        v = idx[k].dropna()
        is_n = k == N
        fig.add_trace(go.Scatter(x=v.index, y=v, name=k, mode="lines", line={"color": charts.MAIN if is_n else charts.CONTEXT, "width": 3 if is_n else 1.5},
                                 hovertemplate=f"{k} %{{x|%Y年%-m月}}までの1年間 %{{y:.0f}}<extra></extra>", showlegend=False))
        fig.add_annotation(x=v.index[-1], y=ends[k], text=f"<b>{k}</b>" if is_n else k, showarrow=False, xanchor="left", xshift=6,
                           font={"size": 12 if is_n else 10})
    fig.add_hline(y=100, line={"color": "rgba(128,128,128,.6)", "width": 1})
    charts.layout(fig, height=380, hovermode="x unified")
    fig.update_yaxes(title="2019年（1〜12月）＝100")
    ui.chart(fig)
    tbl = cur.loc[[N] + peers].assign(
        延べ宿泊者数=lambda x: (x.guests / 1e4).round(0).astype(int).astype(str) + "万人泊",
        コロナ前比=lambda x: x.vs2019.map(lambda v: f"{v:+.0%}"),
        外国人の割合=lambda x: x.foreign_share.map(lambda v: f"{v:.0%}"),
        客室稼働率=lambda x: x.occupancy.map(lambda v: f"{v:.0f}%"),
        全国順位=lambda x: rank.loc[x.index, "guests"].astype(int).astype(str) + "位",
    )[["延べ宿泊者数", "全国順位", "コロナ前比", "外国人の割合", "客室稼働率"]]
    st.dataframe(tbl.rename_axis("都道府県"), use_container_width=True)
    last_idx = idx.iloc[-1][[N] + peers].sort_values(ascending=False)
    ui.readout([
        f"選んだ県の中で、2019年からの回復がいちばん進んでいるのは **{last_idx.index[0]}**（{last_idx.iloc[0]:.0f}）、"
        f"長野県は {list(last_idx.index).index(N) + 1}番目（{last_idx[N]:.0f}）です。" if peers else "比べる県を選んでください。",
        f"選んだ県の中で外国人の割合がいちばん高いのは **{cur.loc[[N] + peers].foreign_share.idxmax()}**（{cur.loc[[N] + peers].foreign_share.max():.0%}）です。" if peers else "",
    ], source=f"観光庁「宿泊旅行統計調査」。表は直近12か月（{period}）")

ui.sources(["shukuhaku"])

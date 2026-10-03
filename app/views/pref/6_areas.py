import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, maps, ui
from lib.charts import man, updown

ui.setup("県内のどこへ？", "長野県内のどの市町村・観光地・エリアに人が訪れているかを見るページです。"
         "ひとつの市町村や広域を詳しく見るときは、上の「市町村」「広域連携」から進めます。")

sp = data.riyousha_spots()
ry = int(sp.year.max())
cur, prev, y19 = sp[sp.year == ry], sp[sp.year == ry - 1], sp[sp.year == 2019]
g = data.municipalities()
muni = g.set_index("code")
by_muni = cur.groupby("municipality_code").total.sum().sort_values(ascending=False)
names = muni.name

ui.insight(
    f"{ry}年に県内の観光地（{len(cur)}か所）を訪れた人は延べ <b>{man(cur.total.sum())}</b>（前年より{updown(cur.total.sum() / prev.total.sum() - 1)}）。"
    f"<b>{names[by_muni.index[0]]}・{names[by_muni.index[1]]}・{names[by_muni.index[2]]}</b> の3市町で県全体の {by_muni.iloc[:3].sum() / by_muni.sum():.0%} を占めます。"
)

# ---- 1. 地図 ----
ui.block("🗾 市町村ごとの観光地の利用者数（地図）",
         f"{ry}年に、それぞれの市町村の観光地を訪れた人の延べ人数。色が濃いほど多い",
         "県内で人が集まっている場所と、まだ少ない場所をひと目でつかみたいとき")
st.plotly_chart(maps.municipality_map(g, outlines=data.kouiki(), values=by_muni.to_dict(),
                                      value_label=f"{ry}年の延べ利用者数", fmt=man), use_container_width=True)
k = cur.merge(muni[["kouiki"]], left_on="municipality_code", right_index=True)
kk = k.groupby("kouiki").total.sum().sort_values(ascending=False)
ui.readout([
    f"利用者がいちばん多い広域は **{kk.index[0]}**（県全体の {kk.iloc[0] / kk.sum():.0%}）、少ないのは **{kk.index[-1]}**（{kk.iloc[-1] / kk.sum():.0%}）です。",
    f"観光地の調査対象がない市町村（灰色）は {len(g) - len(by_muni)} 市町村あります。" if len(g) > len(by_muni) else "",
], source=f"長野県「観光地利用者統計調査」（{ry}年）。{maps.ATTRIBUTION}")

# ---- 2. 観光地ランキング ----
ui.block("🏆 人が多い観光地 トップ15",
         f"{ry}年に延べ利用者数が多かった観光地15か所と、前年からの増減",
         "県を代表する観光地の顔ぶれと、勢いのある観光地を知りたいとき")
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
st.plotly_chart(fig, use_container_width=True)
big = t[(t.total >= 100_000) & (t.ly > 0)].assign(chg=lambda x: x.total / x.ly - 1).sort_values("chg")
ui.readout([
    f"いちばん多いのは **{top.index[-1]}**（{top.municipality.iloc[-1]}, {man(top.total.iloc[-1])}）です。",
    f"トップ15で県全体の {top.total.sum() / cur.total.sum():.0%} を占めます。",
    f"10万人以上の観光地のうち、前年から大きく伸びたのは **{big.index[-1]}**（{big.chg.iloc[-1]:+.0%}）、"
    f"大きく減ったのは **{big.index[0]}**（{big.chg.iloc[0]:+.0%}）です。" if len(big) >= 2 else "",
], source=f"長野県「観光地利用者統計調査」（{ry}年）。（ ）内は前年比")

# ---- 3. 10広域の回復 ----
ui.block("📈 10広域ごとの、コロナ前からの戻り具合",
         f"10広域それぞれの観光地の延べ利用者数を、2019年を100としたときの{ry}年の値",
         "県内で回復が進んでいる地域・遅れている地域を比べたいとき")
k19 = y19.merge(muni[["kouiki"]], left_on="municipality_code", right_index=True).groupby("kouiki").total.sum()
idx = (kk / k19 * 100).sort_values()
allidx = cur.total.sum() / y19.total.sum() * 100
fig = go.Figure(go.Bar(
    y=idx.index, x=idx.values, orientation="h", marker_color=[charts.MAIN if v >= 100 else charts.SECOND for v in idx.values],
    text=[f"{v:.0f}" for v in idx.values], textposition="outside", cliponaxis=False,
    hovertemplate="%{y}: 2019年＝100 として %{x:.0f}<extra></extra>",
))
fig.add_vline(x=100, line={"color": "rgba(128,128,128,.7)", "width": 1})
fig.add_vline(x=allidx, line={"color": charts.CONTEXT, "dash": "dot", "width": 2})
fig.add_annotation(x=allidx, y=1, yref="paper", text=f"県全体 {allidx:.0f}", showarrow=False, yanchor="bottom")
charts.layout(fig, height=380)
fig.update_xaxes(title="2019年＝100", range=[0, idx.max() * 1.18])
fig.update_yaxes(showgrid=False)
st.plotly_chart(fig, use_container_width=True)
ui.readout([
    f"県全体は2019年の **{allidx:.0f}%** の水準です。",
    f"いちばん戻っているのは **{idx.index[-1]}**（{idx.iloc[-1]:.0f}）、いちばん戻りが遅いのは **{idx.index[0]}**（{idx.iloc[0]:.0f}）です。",
    f"2019年を上回っている広域: {'・'.join(idx[idx >= 100].index) or 'なし'}。",
], source="長野県「観光地利用者統計調査」")

# ---- 4. 県内5エリアの宿泊 ----
ui.block("🛏️ 県内5エリアの宿泊者数",
         "観光庁の区分による県内5エリアごとの、最新年の延べ宿泊者数と前年からの増減",
         "日帰りの観光地の数字だけでなく、どのエリアに泊まっているかを確かめたいとき")
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
st.plotly_chart(fig, use_container_width=True)
g2 = (ay.iloc[-1] / ay.iloc[-2] - 1).sort_values()
ui.readout([
    f"{ay.index[-1]}年にいちばん泊まった人が多いのは **{order[0]}** エリア（県全体の {ay.iloc[-1][order[0]] / ay.iloc[-1].sum():.0%}）です。",
    f"前年からの伸びが大きいのは **{g2.index[-1]}**（{g2.iloc[-1]:+.0%}）、小さいのは **{g2.index[0]}**（{g2.iloc[0]:+.0%}）です。",
], source="観光庁「宿泊旅行統計調査」広域市町村（130区分）別参考表")
with st.expander("5エリアに入る市町村"):
    st.dataframe(data.shukuhaku_area_map(), hide_index=True, use_container_width=True)

# ---- 5. 観光地の種類 ----
ui.block("⛰️ 観光地の種類ごとの利用者",
         "山岳・高原・温泉・名所旧跡など、観光地の種類ごとの延べ利用者数と、2019年からの増減",
         "どんなタイプの観光地に人が集まっているか、伸びているかを知りたいとき")
c = pd.DataFrame({"2019年": y19.groupby("category").total.sum(), f"{ry}年": cur.groupby("category").total.sum()})
fig = go.Figure()
for col, color in [("2019年", charts.CONTEXT), (f"{ry}年", charts.MAIN)]:
    fig.add_trace(go.Bar(x=c.index, y=c[col] / 1e4, name=col, marker_color=color, marker_line={"color": "white", "width": 2},
                         hovertemplate=f"%{{x}} {col} %{{y:,.0f}}万人<extra></extra>"))
charts.layout(fig, height=300, barmode="group", bargap=0.3)
fig.update_yaxes(title="延べ利用者数（万人）")
st.plotly_chart(fig, use_container_width=True)
cc = (c[f"{ry}年"] / c["2019年"] - 1).sort_values()
ui.readout([
    f"いちばん多いのは **{c[f'{ry}年'].idxmax()}**（全体の {c[f'{ry}年'].max() / c[f'{ry}年'].sum():.0%}）です。",
    "2019年からの増減: " + "、".join(f"{k} {v:+.0%}" for k, v in cc.items()) + "。",
], source="長野県「観光地利用者統計調査」")

c1, c2 = st.columns(2)
with c1:
    st.page_link("views/2_municipality.py", label="🔍 市町村を選んで詳しく見る →")
with c2:
    st.page_link("views/3_kouiki.py", label="🤝 広域で連携する（広域ごとに見る）→")
ui.sources(["riyousha", "shukuhaku", "boundaries"])

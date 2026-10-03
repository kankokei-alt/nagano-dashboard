import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui
from lib.charts import updown, yen

ui.setup("いくら使っている？", "観光消費額と1人あたりの金額。物価の上がり分を除いた伸びも。")

ir = data.irikomi()
iy = int(ir.year.max())
d = ir[(ir.stay != "計") & (ir.measure != "unit_price")].copy()
d["who"] = "海外の人"
d.loc[(d.purpose != "訪日外国人") & (d.origin == "県内"), "who"] = "県内の人"
d.loc[(d.purpose != "訪日外国人") & (d.origin == "県外"), "who"] = "県外の人"
WHO = [("県内の人", charts.MAIN), ("県外の人", charts.SECOND), ("海外の人", charts.THIRD)]
sp = d[(d.period == "年計") & (d.measure == "spend")].groupby(["year", "who"]).value.sum().unstack()
tot = sp.sum(axis=1)
vis = d[(d.period == "年計") & (d.measure == "visitors")].groupby("year").value.sum()

ui.insight(
    f"{iy}年の観光消費額は <b>{yen(tot[iy])}</b>（前年より{updown(tot[iy] / tot[iy - 1] - 1)}、2019年より{updown(tot[iy] / tot[2019] - 1)}）。"
    f"そのうち県外の人が {sp.loc[iy, '県外の人'] / tot[iy]:.0%}、海外の人が {sp.loc[iy, '海外の人'] / tot[iy]:.0%} を占めます。"
    f"1人あたりでは {tot[iy] / vis[iy]:,.0f}円 で、2019年（{tot[2019] / vis[2019]:,.0f}円）より{updown(tot[iy] / vis[iy] / (tot[2019] / vis[2019]) - 1)}です。"
)

# ---- 1. 推移 ----
ui.block("💴 観光消費額の移り変わり（誰が使ったか）", "観光消費額の推移（誰が使ったか）", "伸びを支える層を知りたいとき")
fig = go.Figure()
for grp, color in WHO:
    fig.add_trace(go.Bar(x=sp.index, y=sp[grp] / 1e8, name=grp, marker_color=color, marker_line={"color": "white", "width": 1},
                         hovertemplate=f"%{{x}}年 {grp} %{{y:,.0f}}億円<extra></extra>"))
charts.layout(fig, height=340, barmode="stack", bargap=0.25, legend_traceorder="normal")
fig.update_yaxes(title="億円")
fig.update_xaxes(dtick=1)
st.plotly_chart(fig, use_container_width=True)
g = sp.loc[iy] - sp.loc[2019]
ui.readout([
    f"2019年から{iy}年にかけての増え方: 県内の人 {g['県内の人'] / 1e8:+,.0f}億円、県外の人 {g['県外の人'] / 1e8:+,.0f}億円、海外の人 {g['海外の人'] / 1e8:+,.0f}億円。",
    f"いちばん増えたのは **{g.idxmax()}** で、増えた分全体の {g.max() / g[g > 0].sum():.0%} を占めます。" if (g > 0).any() else "",
    f"海外の人の割合は 2019年 {sp.loc[2019, '海外の人'] / tot[2019]:.0%} → {iy}年 {sp.loc[iy, '海外の人'] / tot[iy]:.0%} です。",
], source="長野県「観光入込客統計」（観光庁 共通基準）。観光目的とビジネス目的の合計")

# ---- 2. 1人あたりの単価 ----
ui.block("🧾 1人あたり、いくら使うか（観光目的）", "1人1回あたりの消費額（観光目的）", "お金が落ちやすい客層を知りたいとき")
u = ir[(ir.year == iy) & (ir.period == "年計") & (ir.measure == "unit_price")]
segs = [("県内・日帰り", "観光目的", "日帰り", "県内"), ("県外・日帰り", "観光目的", "日帰り", "県外"),
        ("海外・日帰り", "訪日外国人", "日帰り", "観光"), ("県内・宿泊", "観光目的", "宿泊", "県内"),
        ("県外・宿泊", "観光目的", "宿泊", "県外"), ("海外・宿泊", "訪日外国人", "宿泊", "観光")]
up = pd.Series({k: u[(u.purpose == p) & (u.stay == st_) & (u.origin == o)].value.sum() for k, p, st_, o in segs})
color = {"県内": charts.MAIN, "県外": charts.SECOND, "海外": charts.THIRD}
fig = go.Figure(go.Bar(
    y=up.index, x=up.values, orientation="h", marker_color=[color[k[:2]] for k in up.index],
    text=[f"{v:,.0f}円" for v in up.values], textposition="outside", cliponaxis=False,
    hovertemplate="%{y}: 1人あたり %{x:,.0f}円<extra></extra>",
))
charts.layout(fig, height=330)
fig.update_xaxes(title="1人1回あたりの消費額（円）", range=[0, up.max() * 1.25])
fig.update_yaxes(showgrid=False, autorange="reversed")
st.plotly_chart(fig, use_container_width=True)
ui.readout([
    f"いちばん高いのは **{up.idxmax()}**（{up.max():,.0f}円）、いちばん低いのは **{up.idxmin()}**（{up.min():,.0f}円）で、約 {up.max() / up.min():.0f} 倍の差があります。",
    f"県外の人は、日帰りから泊まりに変わると {up['県外・宿泊'] / up['県外・日帰り']:.1f} 倍のお金を使います。",
], source=f"長野県「観光入込客統計」（{iy}年, 観光目的）")

# ---- 3. 単価の推移と物価 ----
ui.block("📈 1人あたりの消費額は、物価以上に増えている？", "1人あたり消費額と物価の伸び（2015年＝100）", "実質的な伸びを確かめたいとき")
ut = ir[(ir.period == "年計") & (ir.measure == "unit_price") & (ir.purpose == "観光目的") & (ir.stay == "宿泊") & (ir.origin == "県外")]
ut = ut.set_index("year").value.reindex(range(int(ir.year.min()), iy + 1))  # 単価が読み取れていない年は空ける
miss = [y for y in ut.index if pd.isna(ut[y]) and y >= 2015]
mc = data.macro()
cpi = mc[["cpi_all", "cpi_hotel"]].groupby(mc.index.year).mean()
cpi = cpi[cpi.index <= iy]
b = 2015
lines = [("県外・宿泊の1人あたり消費額", ut / ut[b] * 100, charts.SECOND, "solid"),
         ("物価（総合）", cpi.cpi_all / cpi.cpi_all[b] * 100, charts.CONTEXT, "solid"),
         ("宿泊料の値段", cpi.cpi_hotel / cpi.cpi_hotel[b] * 100, charts.MAIN, "dot")]
fig = go.Figure()
for label, v, c, dash in lines:
    v = v[v.index >= b]
    fig.add_trace(go.Scatter(x=v.index, y=v, name=label, mode="lines+markers", line={"color": c, "width": 2.5, "dash": dash},
                             connectgaps=False,
                             hovertemplate=f"{label} %{{x}}年 %{{y:.0f}}<extra></extra>"))
    fig.add_annotation(x=v.dropna().index[-1], y=v.dropna().iloc[-1], text=f"<b>{label}</b>", showarrow=False, xanchor="left", xshift=6, font={"size": 11})
fig.add_hline(y=100, line={"color": "rgba(128,128,128,.5)", "width": 1})
charts.layout(fig, height=340, hovermode="x unified", showlegend=False)
fig.update_yaxes(title=f"{b}年＝100")
fig.update_xaxes(dtick=1, range=[b - 0.5, iy + 3])
st.plotly_chart(fig, use_container_width=True)
real = (ut[iy] / ut[b]) / (cpi.cpi_all[iy] / cpi.cpi_all[b]) - 1
ui.readout([
    f"{b}年から{iy}年までに、県外・宿泊の人の1人あたり消費額は {ut[iy] / ut[b] - 1:+.0%}、物価（総合）は {cpi.cpi_all[iy] / cpi.cpi_all[b] - 1:+.0%}、"
    f"宿泊料の値段は {cpi.cpi_hotel[iy] / cpi.cpi_hotel[b] - 1:+.0%} 変わりました。",
    f"物価の上がり分を差し引いた実質では **{real:+.0%}** です。"
    + ("値段が上がった以上に、1人が使うお金が増えています。" if real > 0.03 else
       "伸びのほとんどは値段の上がり分によるものです。" if real > -0.03 else "物価ほどには使うお金が増えていません。"),
    f"{miss[0]}〜{miss[-1]}年は、県の公表資料から1人あたり消費額の表を読み取れていないため空けています。" if miss else "",
], source="長野県「観光入込客統計」、総務省「消費者物価指数」（全国, 2020年基準, e-Stat）。物価は年平均")

# ---- 4. 季節ごとの消費額 ----
ui.block("📅 季節ごとの観光消費額", "3か月ごとの観光消費額", "お金が落ちる季節を知りたいとき")
q = d[(d.year == iy) & (d.period != "年計") & (d.measure == "spend")].groupby(["period", "who"]).value.sum().unstack()
QL = {"Q1": "1〜3月", "Q2": "4〜6月", "Q3": "7〜9月", "Q4": "10〜12月"}
fig = go.Figure()
for grp, c in WHO:
    fig.add_trace(go.Bar(x=[QL[p] for p in q.index], y=q[grp] / 1e8, name=grp, marker_color=c,
                         marker_line={"color": "white", "width": 2}, hovertemplate=f"{grp} %{{x}} %{{y:,.0f}}億円<extra></extra>"))
charts.layout(fig, height=320, barmode="stack", bargap=0.35, legend_traceorder="normal")
fig.update_yaxes(title="億円")
st.plotly_chart(fig, use_container_width=True)
qt = q.sum(axis=1)
qs = q["海外の人"] / qt
ui.readout([
    f"いちばんお金が使われたのは **{QL[qt.idxmax()]}**（{yen(qt.max())}）、いちばん少ないのは **{QL[qt.idxmin()]}**（{yen(qt.min())}）です。",
    f"海外の人が使ったお金の割合は {QL[qs.idxmax()]} がいちばん高く、{qs.max():.0%} です。",
], source=f"長野県「観光入込客統計」（{iy}年）")

ui.sources(["irikomi"])

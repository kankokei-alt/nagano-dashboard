import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui
from lib.charts import man, updown

ui.setup("いつ来ている？", "長野県の観光の「季節の波」を見るページです。月ごとの多い・少ない、日本人と外国人の違い、"
         "観光地の種類ごとの違い、休日や雪との関係を見ます。")

s = data.shukuhaku()
last = s.index.max()
fy = last.year - 1  # 1年分そろっている最新の年
full = s[s.index.year == fy]
MONTHS = [f"{m}月" for m in range(1, 13)]

ui.insight(
    f"{fy}年に長野県でいちばん泊まった人が多かったのは <b>{full.guests.idxmax().month}月</b>（年間の{full.guests.max() / full.guests.sum():.0%}）、"
    f"少なかったのは <b>{full.guests.idxmin().month}月</b>（{full.guests.min() / full.guests.sum():.0%}）で、"
    f"多い月は少ない月の約 {full.guests.max() / full.guests.min():.1f} 倍です。"
    f"日本人は{full.japanese.idxmax().month}月、外国人は{full.foreign.idxmax().month}月がいちばん多く、季節の山がずれています。"
)

# ---- 1. 月ごとの宿泊者数 ----
ui.block("📊 月ごとの延べ宿泊者数（今年・前年・コロナ前）",
         "長野県に泊まった人の延べ人数を月ごとに並べ、今年・前年・2019年（コロナ前）を重ねたもの",
         "繁忙期と閑散期をつかみたいとき／今年のある月が例年より多いか少ないかを確かめたいとき")
fig = go.Figure()
for y, label, color, dash in [(2019, "2019年（コロナ前）", charts.CONTEXT, "dot"), (fy, f"{fy}年", charts.CONTEXT, "solid"),
                              (last.year, f"{last.year}年", charts.MAIN, "solid")]:
    d = s[s.index.year == y]
    fig.add_trace(go.Scatter(x=d.index.month, y=d.guests / 1e4, name=label, mode="lines+markers",
                             line={"color": color, "width": 3 if y == last.year else 2, "dash": dash},
                             hovertemplate=f"{label} %{{x}}月 %{{y:,.0f}}万人泊<extra></extra>"))
charts.layout(fig, height=340, hovermode="x unified")
fig.update_xaxes(tickvals=list(range(1, 13)), ticktext=MONTHS)
fig.update_yaxes(title="延べ宿泊者数（万人泊）", rangemode="tozero")
st.plotly_chart(fig, use_container_width=True)
cy = s[s.index.year == last.year].guests
prev = s[s.index.year == fy].guests
diff = pd.Series(cy.values / prev.values[: len(cy)] - 1, index=cy.index.month)
ui.readout([
    f"{fy}年は **{full.guests.idxmax().month}月**" + ("（夏休み）" if full.guests.idxmax().month == 8 else "") + "がいちばん多く、"
    f"次いで {full.guests.drop(full.guests.idxmax()).idxmax().month}月です。",
    f"{last.year}年に入ってから前年を上回った月: {'、'.join(f'{m}月' for m in diff[diff > 0.005].index) or 'なし'}／"
    f"下回った月: {'、'.join(f'{m}月' for m in diff[diff < -0.005].index) or 'なし'}。",
], source="観光庁「宿泊旅行統計調査」" + ("（今年は速報値。層化基準の見直しの影響を含むことがあります）" if s.loc[last].status == "速報" else ""))

# ---- 2. 日本人と外国人の季節 ----
ui.block("🎌 日本人と外国人で、季節の山が違う",
         f"{fy}年の1年間の宿泊を100%としたとき、各月が何%を占めるかを、日本人と外国人で比べたもの",
         "閑散期を埋めるのに、どちらのお客さまに働きかけるとよいかを考えるとき")
sh = full[["japanese", "foreign"]] / full[["japanese", "foreign"]].sum()
fig = go.Figure()
for col, label, color in [("japanese", "日本人", charts.MAIN), ("foreign", "外国人", charts.SECOND)]:
    fig.add_trace(go.Bar(x=MONTHS, y=sh[col], name=label, marker_color=color, marker_line={"color": "white", "width": 1},
                         hovertemplate=f"{label} %{{x}}: 1年の %{{y:.1%}}<extra></extra>"))
charts.layout(fig, height=320, barmode="group", bargap=0.25)
fig.update_yaxes(tickformat=".0%", title="1年に占める割合")
st.plotly_chart(fig, use_container_width=True)
fw = sh.foreign[sh.index.month.isin([12, 1, 2])].sum()
jw = sh.japanese[sh.index.month.isin([12, 1, 2])].sum()
lowj = sh.japanese.nsmallest(3).index.month
ui.readout([
    f"冬（12〜2月）の3か月に、外国人は1年の **{fw:.0%}** が集中しますが、日本人は {jw:.0%} です。",
    f"日本人がいちばん少ないのは {'・'.join(f'{m}月' for m in sorted(lowj))} です。"
    + (f"このうち外国人の割合が平均より高い月（{'・'.join(f'{m}月' for m in sorted(lowj) if sh.foreign.loc[sh.index.month == m].iloc[0] > 1 / 12)}）は、海外への働きかけで埋められる可能性があります。"
       if any(sh.foreign.loc[sh.index.month == m].iloc[0] > 1 / 12 for m in lowj) else ""),
], source=f"観光庁「宿泊旅行統計調査」（{fy}年）")

# ---- 3. 観光地の種類ごとの季節 ----
ui.block("⛰️ 観光地の種類ごとの季節",
         "県の観光地利用者統計で、観光地の種類（山岳・高原・温泉・名所旧跡）ごとに、何月に人が多いか（1年を100%とした割合）",
         "自分の地域の観光地の「売り」の季節と、手薄な季節を確かめたいとき")
sp = data.riyousha_spots()
ry = int(sp.year.max())
cat = sp[sp.year == ry].groupby("category")[charts.MONTHS].sum()
cat = cat.div(cat.sum(axis=1), axis=0)
fig = go.Figure(go.Heatmap(
    z=cat.values, x=MONTHS, y=cat.index, colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]], zmin=0,
    text=[[f"{v:.0%}" for v in r] for r in cat.values], texttemplate="%{text}", xgap=2, ygap=2,
    hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "1年に<br>占める割合", "tickformat": ".0%"},
))
charts.layout(fig, height=260)
fig.update_xaxes(side="top")
fig.update_yaxes(showgrid=False)
st.plotly_chart(fig, use_container_width=True)
pk = cat.idxmax(axis=1).str[1:].astype(int)
ui.readout([
    "それぞれいちばん多い月: " + "、".join(f"{c} {m}月（{cat.loc[c].max():.0%}）" for c, m in pk.items()) + "。",
    f"季節の差がいちばん大きいのは **{(cat.max(axis=1) / cat.min(axis=1)).idxmax()}**、"
    f"いちばん小さい（1年を通して来る）のは **{(cat.max(axis=1) / cat.min(axis=1)).idxmin()}** です。",
], source=f"長野県「観光地利用者統計調査」（{ry}年）。スキー場は調査の対象外のため含まれていません")

# ---- 4. 雪と冬の宿泊 ----
ui.block("❄️ 雪の多い冬は、泊まる人も多い？",
         "冬（12〜3月）の宿泊者数の前年比と、その冬のスキー場の多い地点（白馬・野沢温泉・菅平）の最深積雪の関係",
         "雪不足の冬にどのくらい影響が出そうかの目安がほしいとき")
wx = data.weather()
ski = wx[wx.station.isin(["白馬", "野沢温泉", "菅平"])].copy()
ski["season"] = ski.ym.dt.year + (ski.ym.dt.month >= 8)
snow = ski[ski.ym.dt.month.isin([12, 1, 2, 3])].groupby(["season", "station"]).snow_depth_max.max().unstack()
snow = snow[snow.index >= ski.ym.min().year + 1]
snow_ratio = (snow / snow.mean()).mean(axis=1)  # 地点ごとの平均に対する比を平均
g = s.copy()
g["season"] = g.index.year + (g.index.month >= 8)
win = g[g.index.month.isin([12, 1, 2, 3])].groupby("season").guests.sum()
cnt = g[g.index.month.isin([12, 1, 2, 3])].groupby("season").guests.size()
win = win[cnt == 4]
yoy = win / win.shift(1) - 1
ev = data.events()
covid = ev[ev.kind == "covid"]
# コロナの冬と、回復途中・旅行支援があった冬を比べる相手にする冬（前年比が乱れる）
bad = set(range(covid.start.min().year, covid.end.max().year + 3))
pts = pd.DataFrame({"snow": snow_ratio, "yoy": yoy}).dropna()
pts = pts[~pts.index.isin(bad)]
fig = go.Figure(go.Scatter(
    x=pts.snow, y=pts.yoy, mode="markers+text", text=[f"{y - 1}〜{y % 100:02d}" for y in pts.index],
    textposition="top center", marker={"size": 11, "color": charts.MAIN, "line": {"color": "white", "width": 2}},
    hovertemplate="%{text}年の冬<br>積雪 平年の %{x:.0%}<br>宿泊者数 前年比 %{y:+.1%}<extra></extra>",
))
fig.add_hline(y=0, line={"color": "rgba(128,128,128,.6)", "width": 1})
fig.add_vline(x=1, line={"color": "rgba(128,128,128,.6)", "width": 1, "dash": "dot"})
charts.layout(fig, height=360, showlegend=False)
fig.update_xaxes(title="その冬の最深積雪（3地点の平均に対する割合）", tickformat=".0%")
fig.update_yaxes(title="冬（12〜3月）の延べ宿泊者数 前年比", tickformat="+.0%")
st.plotly_chart(fig, use_container_width=True)
r = float(np.corrcoef(pts.snow, pts.yoy)[0, 1]) if len(pts) >= 5 else float("nan")
low = pts[pts.snow < 0.8]
ui.readout([
    f"コロナの影響を受けた冬を除く {len(pts)} 回の冬で見ると、雪の多さと宿泊の伸びの関係（相関係数）は **{r:+.2f}** です。"
    + ("雪が多い冬ほど宿泊も伸びる傾向がはっきり見られます。" if r >= 0.5 else
       "雪が多い冬ほど宿泊も伸びるという、ゆるやかな傾向があります。" if r >= 0.25 else
       "県全体の宿泊者数では、雪の多さとのはっきりした関係は見られません（スキー場の多い地域に限ると違う可能性があります）。"),
    (f"雪が平年の8割に届かなかった冬（{'、'.join(f'{y - 1}〜{y % 100:02d}年' for y in low.index)}）の宿泊者数の前年比は、"
     f"平均 {low.yoy.mean():+.1%} でした。") if len(low) else "",
], source="気象庁「過去の気象データ」、観光庁「宿泊旅行統計調査」")

# ---- 5. この先の休日カレンダー ----
ui.block("🗓️ この先12か月の休みの多さ",
         "これからの各月の休日（土日・祝日・年末年始）の数が、例年（2015〜2025年の平均）より多いか少ないか",
         "連休の多い月に合わせた企画や、休みの少ない月の早めの販促を考えるとき")
cal = data.calendar_monthly()
cal["month"] = pd.to_datetime(cal.month)
cal["m"] = cal.month.dt.month
normal = cal[(cal.month >= "2015-01-01") & (cal.month < "2026-01-01")].groupby("m").off_days.mean()
start = pd.Timestamp.today().normalize().replace(day=1)
ahead = cal[(cal.month >= start) & (cal.month < start + pd.DateOffset(months=12))].copy()
ahead["diff"] = ahead.off_days - ahead.m.map(normal)
ahead["label"] = ahead.month.dt.strftime("%Y年%-m月")
fig = go.Figure(go.Bar(
    x=ahead.label, y=ahead["diff"],
    marker_color=[charts.MAIN if d > 0.5 else charts.SECOND if d < -0.5 else charts.CONTEXT for d in ahead["diff"]],
    customdata=ahead[["off_days", "long_weekends", "max_off_run"]].values,
    hovertemplate="<b>%{x}</b><br>例年との差 %{y:+.1f} 日<br>休日 %{customdata[0]} 日／3連休以上 %{customdata[1]} 回／最長 %{customdata[2]} 連休<extra></extra>",
))
charts.layout(fig, height=300)
fig.update_yaxes(title="例年との差（日）", zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
st.plotly_chart(fig, use_container_width=True)
best = ahead.sort_values(["diff", "long_weekends"], ascending=False).iloc[0]
worst = ahead.sort_values(["diff", "long_weekends"]).iloc[0]
ui.readout([
    f"休みがいちばん多いのは **{best.label}**（例年より {best['diff']:+.1f} 日、3連休以上 {int(best.long_weekends)} 回、最長 {int(best.max_off_run)} 連休）。",
    f"いちばん少ないのは **{worst.label}**（例年より {worst['diff']:+.1f} 日）です。",
], source="内閣府「国民の祝日」。年末年始（12/29〜1/3）も休日として数えています")

ui.sources(["shukuhaku", "riyousha", "weather", "holidays"])

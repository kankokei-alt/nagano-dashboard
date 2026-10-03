import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui
from lib.charts import man, pct, updown, yen

ui.setup("長野県の全体像", "長野県の観光の「いま」と「これまで」を大づかみにするページです。"
         "下の窓から、知りたいテーマの詳しいページに進めます。")

# ---- データ ----
s = data.shukuhaku()
last = s.index.max()
ly, pre = last - pd.DateOffset(years=1), last.replace(year=2019)
cur = s.loc[last]
ym = f"{last.year}年{last.month}月"
roll = s.guests.rolling(12).sum()  # 直近12か月の合計（季節の波をならす）
ann = s[s.index.year < last.year].groupby(s.index.year[s.index.year < last.year])[["japanese", "foreign"]].sum()
ytd = s[(s.index.year == last.year)].guests.sum()
ytd_ly = s[(s.index.year == last.year - 1) & (s.index.month <= last.month)].guests.sum()

ir = data.irikomi()
yr = ir[(ir.period == "年計") & (ir.stay == "計")].groupby(["year", "measure"]).value.sum().unstack()
iy = int(yr.index.max())

# ---- ここがポイント ----
ui.insight(
    f"{ym}までの1年間に、長野県には延べ <b>{man(roll[last], '人泊')}</b> が泊まりました"
    f"（前年の同じ期間より{updown(roll[last] / roll[ly] - 1)}、コロナ前の2019年の同じ期間より{updown(roll[last] / roll[pre] - 1)}）。"
    f"<br>{iy}年に県を訪れた人は実人数で <b>{man(yr.loc[iy, 'visitors'])}</b>、"
    f"使ったお金（観光消費額）は <b>{yen(yr.loc[iy, 'spend'])}</b> で、"
    f"1人あたりでは {yr.loc[iy, 'spend'] / yr.loc[iy, 'visitors']:,.0f}円 でした。"
)

cols = st.columns(4)
with cols[0]:
    ui.kpi(f"延べ宿泊者数（{ym}）", man(cur.guests, "人泊"), f"前年同月比 {pct(cur.guests / s.loc[ly].guests - 1)}")
with cols[1]:
    ui.kpi(f"延べ宿泊者数（直近12か月）", man(roll[last], "人泊"), f"前年同期比 {pct(roll[last] / roll[ly] - 1)}")
with cols[2]:
    ui.kpi(f"県を訪れた人（{iy}年, 実人数）", man(yr.loc[iy, "visitors"]),
           f"前年比 {pct(yr.loc[iy, 'visitors'] / yr.loc[iy - 1, 'visitors'] - 1)}")
with cols[3]:
    ui.kpi(f"観光消費額（{iy}年）", yen(yr.loc[iy, "spend"]), f"前年比 {pct(yr.loc[iy, 'spend'] / yr.loc[iy - 1, 'spend'] - 1)}")
if cur.status == "速報":
    st.caption(f"※ {last.year}年の宿泊の数字は速報値です。{last.year}年1月分から調査の区分け（層化基準）が変わったため、"
               "前年との比較には見直しの影響が含まれることがあります（観光庁）。")

# ---- A. 年ごとの推移 ----
ui.block("📊 長野県に泊まった人の数（年ごと）",
         "長野県のホテル・旅館などに泊まった人の延べ人数（1人が2泊すれば2人泊）が、年ごとにどう変わってきたか",
         "長野県の観光の規模が、10年前やコロナ前と比べて大きくなっているのか・小さくなっているのかを知りたいとき")
fig = go.Figure()
for col, label, color in [("japanese", "日本人", charts.MAIN), ("foreign", "外国人", charts.SECOND)]:
    fig.add_trace(go.Bar(x=ann.index, y=ann[col] / 1e4, name=label, marker_color=color,
                         marker_line={"color": "white", "width": 1},
                         hovertemplate=f"%{{x}}年 {label} %{{y:,.0f}}万人泊<extra></extra>"))
charts.layout(fig, height=340, barmode="stack", bargap=0.25)
fig.update_yaxes(title="延べ宿泊者数（万人泊）")
fig.update_xaxes(dtick=1)
st.plotly_chart(fig, use_container_width=True)
tot = ann.sum(axis=1)
normal = tot.drop([2020, 2021, 2022], errors="ignore")
best = tot.idxmax()
ui.readout([
    f"コロナ禍（2020〜22年）を除くと、年 {man(normal.min(), '人泊')}〜{man(normal.max(), '人泊')} の間で推移しています。いちばん多かったのは **{best}年**（{man(tot[best], '人泊')}）です。",
    f"{tot.index[-1]}年は {man(tot.iloc[-1], '人泊')} で、コロナ前の2019年と比べて{updown(tot.iloc[-1] / tot[2019] - 1)}。",
    f"外国人は {ann.index[0]}年の {man(ann.foreign.iloc[0], '人泊')} から {ann.index[-1]}年の {man(ann.foreign.iloc[-1], '人泊')} へ"
    f"約 {ann.foreign.iloc[-1] / ann.foreign.iloc[0]:.0f} 倍になり、全体の {ann.foreign.iloc[-1] / tot.iloc[-1]:.0%} を占めるようになりました。",
    f"{last.year}年は1〜{last.month}月で {man(ytd, '人泊')}（前年の同じ期間より{updown(ytd / ytd_ly - 1)}）です。",
], source="観光庁「宿泊旅行統計調査」")

# ---- B. 直近12か月の合計 ----
ui.block("📈 季節の波をならした「いまの勢い」",
         "各月までの1年間（直近12か月）の延べ宿泊者数の合計。季節による増減をならして、長い目での上り下りが見える",
         "最近の宿泊が「伸びている途中」なのか「頭打ち」なのかをつかみたいとき")
r = roll.dropna()
fig = go.Figure()
fig.add_trace(go.Scatter(x=r.index, y=r / 1e4, mode="lines", line={"color": charts.MAIN, "width": 3},
                         name="直近12か月の合計", hovertemplate="%{x|%Y年%-m月}までの1年間 %{y:,.0f}万人泊<extra></extra>"))
v19 = roll[pre]  # 2019年の同じ時期までの1年間
fig.add_hline(y=v19 / 1e4, line={"color": charts.CONTEXT, "dash": "dot", "width": 2})
fig.add_annotation(x=pd.Timestamp(2021, 6, 1), y=v19 / 1e4, text=f"2019年{pre.month}月までの1年間（コロナ前）",
                   showarrow=False, yanchor="bottom", yshift=4, font={"size": 12})
charts.layout(fig, height=320, showlegend=False)
fig.update_yaxes(title="直近12か月の合計（万人泊）", rangemode="tozero")
st.plotly_chart(fig, use_container_width=True)
peak = r.idxmax()
trend6 = r.iloc[-1] / r.iloc[-7] - 1
ui.readout([
    f"{ym}までの1年間は {man(r.iloc[-1], '人泊')} で、コロナ前の同じ時期（2019年{pre.month}月までの1年間, {man(v19, '人泊')}）の **{r.iloc[-1] / v19:.0%}** です。",
    f"過去でいちばん多かったのは {peak.year}年{peak.month}月までの1年間（{man(r[peak], '人泊')}）です。",
    "この半年の動きは"
    + ("、**上向き**です（半年前より" + f"{updown(trend6)}）。" if trend6 > 0.01 else
       "、**下向き**です（半年前より" + f"{updown(trend6)}）。" if trend6 < -0.01 else "、**横ばい**です。"),
], source="観光庁「宿泊旅行統計調査」をもとに計算")

# ---- C. 訪れた人と使ったお金 ----
ui.block("💴 県を訪れた人の数と、使ったお金（年ごと）",
         "日帰りも含めて長野県を訪れた人の実人数と、その人たちが県内で使ったお金（観光消費額）",
         "観光が地域にもたらしている経済効果の大きさや、その増え方を知りたいとき")
c1, c2 = st.columns(2)
for col, key, title, unit, fmt in [(c1, "visitors", "県を訪れた人（実人数）", "万人", lambda v: f"{v / 1e4:,.0f}万人"),
                                   (c2, "spend", "観光消費額", "億円", lambda v: yen(v))]:
    v = yr[key].dropna()
    fig = go.Figure(go.Bar(x=v.index, y=v / (1e4 if key == "visitors" else 1e8), marker_color=charts.MAIN,
                           customdata=[fmt(x) for x in v], hovertemplate="%{x}年 %{customdata}<extra></extra>"))
    charts.layout(fig, height=280, bargap=0.25, title={"text": title, "font": {"size": 14}})
    fig.update_yaxes(title=unit)
    fig.update_xaxes(dtick=2)
    with col:
        st.plotly_chart(fig, use_container_width=True)
first = int(yr.index.min())
per = yr.spend / yr.visitors
ui.readout([
    f"{first}年から{iy}年にかけて、訪れた人の数は {yr.visitors[iy] / yr.visitors[first]:.2f} 倍、"
    f"使ったお金は {yr.spend[iy] / yr.spend[first]:.2f} 倍になりました。",
    f"1人あたりに直すと {per[first]:,.0f}円 → **{per[iy]:,.0f}円**。"
    + ("人数よりもお金の伸びが大きく、**1人あたりの消費が増えたことが伸びの中心**です。"
       if yr.spend[iy] / yr.spend[first] > yr.visitors[iy] / yr.visitors[first] + 0.1 else ""),
], source="長野県「観光入込客統計」（観光庁 共通基準）。2010〜2015年のビジネス目的、2017・2018年の入込客数は参考値")

# ---- 窓 ----
st.markdown('<div class="blk"><h3>🔎 テーマごとに詳しく見る</h3></div>', unsafe_allow_html=True)

grp = ir[(ir.year == iy) & (ir.period == "年計") & (ir.stay != "計") & (ir.measure != "unit_price")]
kengai = grp[(grp.purpose != "訪日外国人") & (grp.origin == "県外")].groupby("measure").value.sum() / grp.groupby("measure").value.sum()
nat = data.shukuhaku_nationality()
ny = int(nat.ym.dt.year.max())
topc = nat[nat.ym.dt.year == ny].groupby("country").value.sum().drop("その他", errors="ignore").idxmax()
f12 = s.foreign.rolling(12).sum()
full = s[s.index.year == last.year - 1].guests
occ_nat = data.shukuhaku("00").loc[last, "occupancy"]
sp = data.riyousha_spots()
ry = int(sp.year.max())
top3 = sp[sp.year == ry].groupby("municipality").total.sum().nlargest(3).index
allp = data.shukuhaku_all()
allp = allp[(allp.metric == "guests") & (allp.pref_code != "00")]
rk = allp[allp.ym > last - pd.DateOffset(months=12)].groupby("pref_name").value.sum().rank(ascending=False)
fc = data.forecast()
nx = fc[fc.facility == "計"].sort_values("ym").iloc[0]

wins = [
    ("visitors", "👥", "誰が来ている？", "県内・県外・海外、日帰りと宿泊", f"県外の人が人数の {kengai['visitors']:.0%}、使ったお金の {kengai['spend']:.0%} を占めます（{iy}年）。", "views/pref/1_visitors.py"),
    ("inbound", "🌏", "海外からのお客さまは？", "国・地域別、季節、全国の動き", f"{ny}年にいちばん多く泊まったのは <b>{topc}</b>。外国人の宿泊は直近12か月で前年より{updown(f12[last] / f12[ly] - 1)}。", "views/pref/2_inbound.py"),
    ("season", "📅", "いつ来ている？", "月ごとの波、日本人と外国人の違い", f"{last.year - 1}年にいちばん多かったのは <b>{full.idxmax().month}月</b>（年間の {full.max() / full.sum():.0%}）。", "views/pref/3_season.py"),
    ("stay", "🛏️", "宿と稼働率", "宿の種類ごとの客室稼働率", f"{ym}の客室稼働率は <b>{cur.occupancy:.1f}%</b>（全国 {occ_nat:.1f}%）。", "views/pref/4_stay.py"),
    ("spend", "💴", "いくら使っている？", "観光消費額と1人あたりの単価", f"{iy}年の観光消費額は <b>{yen(yr.loc[iy, 'spend'])}</b>（前年より{updown(yr.loc[iy, 'spend'] / yr.loc[iy - 1, 'spend'] - 1)}）。", "views/pref/5_spend.py"),
    ("areas", "📍", "県内のどこへ？", "地図、観光地、県内5エリア", f"観光地の延べ利用者が多いのは {'・'.join(top3)}（{ry}年）。", "views/pref/6_areas.py"),
    ("compare", "🏔️", "他の県と比べると？", "全国の中での長野県の位置", f"延べ宿泊者数は直近12か月で <b>全国{int(rk['長野県'])}位</b>。", "views/pref/7_compare.py"),
    ("forecast", "📈", "これからどうなる？", "客室稼働率の12か月先までの見通し", f"{nx.ym.year}年{nx.ym.month}月の客室稼働率は <b>{nx.pred:.0f}%前後</b> の見込み。", "views/pref/8_forecast.py"),
]
for i in range(0, len(wins), 4):
    cols = st.columns(4)
    for c, w in zip(cols, wins[i:i + 4]):
        with c:
            ui.window(*w)

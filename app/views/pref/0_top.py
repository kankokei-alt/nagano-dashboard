import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts, data, ui
from lib.charts import man, pct, updown, yen

ui.setup("長野県の全体像", "今年の進み具合と、これまでの実績。下のテーマから詳しいページに進めます。")

# ---- データ ----
s = data.shukuhaku()
last = s.index.max()
ly = last - pd.DateOffset(years=1)
cur = s.loc[last]
Y, M = last.year, last.month
ym = f"{Y}年{M}月"
ann = s[s.index.year < Y].groupby(s.index.year[s.index.year < Y])[["japanese", "foreign"]].sum()
cum = s.guests.groupby(s.index.year).cumsum()  # 1月からの積み上げ
ytd = cum[last]
ytd_ly = cum[ly]
ytd_19 = cum[last.replace(year=2019)]
full_ly = ann.loc[Y - 1].sum()

ir = data.irikomi()
yr = ir[(ir.period == "年計") & (ir.stay == "計")].groupby(["year", "measure"]).value.sum().unstack()
iy = int(yr.index.max())

fytd = s.foreign.groupby(s.index.year).cumsum()
occ_ytd = s[s.index.year == Y].occupancy.mean()
occ_ytd_ly = s[(s.index.year == Y - 1) & (s.index.month <= M)].occupancy.mean()
done = ann.sum(axis=1)  # 年間の延べ宿泊者数（確定した年）
per = yr.spend / yr.visitors

# ---- ここがポイント ----
ui.insight(
    f"<b>{Y}年（1〜{M}月）</b> 延べ <b>{man(ytd, '人泊')}</b> が泊まり、前年の同じ時期より <b>{updown(ytd / ytd_ly - 1)}</b>。"
    f"{Y - 1}年1年間の {ytd / full_ly:.0%} まで来ています。"
    f"<br><b>{iy}年（年間）</b> 県を訪れた人は実人数で <b>{man(yr.loc[iy, 'visitors'])}</b>（前年より{updown(yr.loc[iy, 'visitors'] / yr.loc[iy - 1, 'visitors'] - 1)}）、"
    f"観光消費額は <b>{yen(yr.loc[iy, 'spend'])}</b>（前年より{updown(yr.loc[iy, 'spend'] / yr.loc[iy - 1, 'spend'] - 1)}）でした。"
)

# ---- 今年の状況 ----
ui.group(f"{Y}年の状況", f"1〜{M}月の累計・速報値。比べる相手は前年の同じ時期")
cols = st.columns(4)
with cols[0]:
    ui.kpi(f"延べ宿泊者数（1〜{M}月）", man(ytd, "人泊"), f"前年同期 {man(ytd_ly, '人泊')}", ytd / ytd_ly - 1)
with cols[1]:
    sh, sh_ly = fytd[last] / ytd, fytd[ly] / ytd_ly
    ui.kpi(f"インバウンド割合（1〜{M}月）", f"{sh:.1%}", f"外国人 {man(fytd[last], '人泊')}／前年同期 {sh_ly:.1%}",
           (sh - sh_ly) * 100, "pt")
with cols[2]:
    ui.kpi(f"客室稼働率（1〜{M}月の平均）", f"{occ_ytd:.1f}%", f"前年同期 {occ_ytd_ly:.1f}%", occ_ytd - occ_ytd_ly, "pt")
with cols[3]:
    ui.kpi(f"延べ宿泊者数（{M}月）", man(cur.guests, "人泊"), "前年同月比", cur.guests / s.loc[ly].guests - 1)
if cur.status == "速報":
    st.caption(f"{Y}年の宿泊の数字は速報値です。{Y}年1月分から調査の区分け（層化基準）が変わったため、"
               "前年との比較には見直しの影響が含まれることがあります（観光庁）。")

# ---- A. 今年の積み上げ ----
with ui.card():
    ui.block(f"{Y}年の延べ宿泊者数（累計）", "1月からの積み上げを前年・2019年と比較")
    fig = go.Figure()
    for y, label, color, dash, width in [(2019, "2019年（コロナ前）", charts.CONTEXT, "dot", 2),
                                         (Y - 1, f"{Y - 1}年", charts.CONTEXT, "solid", 2), (Y, f"{Y}年", charts.MAIN, "solid", 4)]:
        v = cum[cum.index.year == y]
        fig.add_trace(go.Scatter(x=v.index.month, y=v / 1e4, name=label, mode="lines+markers",
                                 line={"color": color, "width": width, "dash": dash}, marker={"size": 8 if y == Y else 5},
                                 hovertemplate=f"{label} 1〜%{{x}}月の累計 %{{y:,.0f}}万人泊<extra></extra>"))
    fig.add_annotation(x=M, y=ytd / 1e4, text=f"<b>{M}月まで {man(ytd, '人泊')}</b><br>前年同期比 {pct(ytd / ytd_ly - 1)}",
                       showarrow=True, arrowhead=0, ax=-70, ay=-50, align="left", font={"size": 12})
    charts.layout(fig, height=360, hovermode="x unified")
    fig.update_xaxes(tickvals=list(range(1, 13)), ticktext=[f"{m}月" for m in range(1, 13)], range=[0.6, 12.4])
    fig.update_yaxes(title="1月からの累計（万人泊）", rangemode="tozero")
    mon = s[s.index.year == Y].guests
    mon_ly = s[(s.index.year == Y - 1) & (s.index.month <= M)].guests
    chg = pd.Series(mon.values / mon_ly.values - 1, index=mon.index.month)
    c1, c2 = st.columns([3, 2])
    with c1:
        ui.chart(fig)
    with c2:
        f2 = go.Figure(go.Bar(
            x=[f"{m}月" for m in chg.index], y=chg.values,
            marker_color=[charts.MAIN if v >= 0 else charts.SECOND for v in chg.values],
            text=[f"{v:+.1%}" for v in chg.values], textposition="outside", cliponaxis=False,
            customdata=list(zip(mon.values / 1e4, mon_ly.values / 1e4)),
            hovertemplate="%{x}: 前年同月比 %{y:+.1%}<br>" + f"{Y}年" + " %{customdata[0]:,.0f}万人泊／" + f"{Y - 1}年" + " %{customdata[1]:,.0f}万人泊<extra></extra>",
        ))
        lim = max(abs(chg).max() * 1.4, 0.05)
        charts.layout(f2, height=360, title={"text": "月ごとの前年同月比", "font": {"size": 14}})
        f2.update_yaxes(tickformat="+.0%", range=[-lim, lim], zeroline=True, zerolinecolor="rgba(128,128,128,.6)")
        ui.chart(f2)
    up_m, dn_m, eq_m = chg[chg >= 0.005].index, chg[chg <= -0.005].index, chg[chg.abs() < 0.005].index
    ui.readout([
        f"{M}月までの累計は {man(ytd, '人泊')} で、前年の同じ時期より **{updown(ytd / ytd_ly - 1)}**（差 {(ytd - ytd_ly) / 1e4:+,.0f}万人泊）です。",
        f"月ごとに見ると、前年を上回ったのは {'・'.join(f'{m}月' for m in up_m) or 'なし'}、"
        + (f"ほぼ前年並み（±0.5%未満）は {'・'.join(f'{m}月' for m in eq_m)}、" if len(eq_m) else "")
        + f"下回ったのは {'・'.join(f'{m}月' for m in dn_m) or 'なし'} です。",
        f"{Y - 1}年は1年間で {man(full_ly, '人泊')} でした。{Y}年は{M}月までにその **{ytd / full_ly:.0%}** まで来ています"
        f"（{Y - 1}年の{M}月時点は {ytd_ly / full_ly:.0%}）。",
    ], source="観光庁「宿泊旅行統計調査」" + (f"（{Y}年は速報値）" if cur.status == "速報" else ""))

# ---- 年間の実績 ----
ui.group(f"{iy}年の実績" if iy == Y - 1 else "年間の実績", "1年間の合計・確定値。比べる相手は前の年")
cols = st.columns(4)
with cols[0]:
    ui.kpi(f"延べ宿泊者数（{Y - 1}年）", man(done[Y - 1], "人泊"), f"{Y - 2}年 {man(done[Y - 2], '人泊')}", done[Y - 1] / done[Y - 2] - 1)
with cols[1]:
    ui.kpi(f"県を訪れた人（{iy}年・実人数）", man(yr.loc[iy, "visitors"]), f"{iy - 1}年 {man(yr.loc[iy - 1, 'visitors'])}",
           yr.loc[iy, "visitors"] / yr.loc[iy - 1, "visitors"] - 1)
with cols[2]:
    ui.kpi(f"観光消費額（{iy}年）", yen(yr.loc[iy, "spend"]), f"{iy - 1}年 {yen(yr.loc[iy - 1, 'spend'])}",
           yr.loc[iy, "spend"] / yr.loc[iy - 1, "spend"] - 1)
with cols[3]:
    ui.kpi(f"1人あたり消費額（{iy}年）", f"{per[iy]:,.0f}円", f"{iy - 1}年 {per[iy - 1]:,.0f}円", per[iy] / per[iy - 1] - 1)

# ---- B. 年ごとの推移 ----
with ui.card():
    ui.block("延べ宿泊者数の推移", "日本人・外国人別、年ごと")
    fig = go.Figure()
    for col, label, color in [("japanese", "日本人", charts.MAIN), ("foreign", "外国人", charts.SECOND)]:
        fig.add_trace(go.Bar(x=ann.index, y=ann[col] / 1e4, name=label, marker_color=color,
                             marker_line={"color": "white", "width": 1},
                             hovertemplate=f"%{{x}}年 {label} %{{y:,.0f}}万人泊<extra></extra>"))
    charts.layout(fig, height=340, barmode="stack", bargap=0.25)
    fig.update_yaxes(title="延べ宿泊者数（万人泊）")
    fig.update_xaxes(dtick=1)
    ui.chart(fig)
    tot = ann.sum(axis=1)
    normal = tot.drop([2020, 2021, 2022], errors="ignore")
    best = tot.idxmax()
    ui.readout([
        f"コロナ禍（2020〜22年）を除くと、年 {man(normal.min(), '人泊')}〜{man(normal.max(), '人泊')} で推移。最多は **{best}年**（{man(tot[best], '人泊')}）です。",
        f"{tot.index[-1]}年は {man(tot.iloc[-1], '人泊')} で、2019年より{updown(tot.iloc[-1] / tot[2019] - 1)}。",
        f"外国人は {ann.index[0]}年から約 {ann.foreign.iloc[-1] / ann.foreign.iloc[0]:.0f} 倍になり、全体の {ann.foreign.iloc[-1] / tot.iloc[-1]:.0%} を占めます。",
    ], source="観光庁「宿泊旅行統計調査」")

# ---- C. 訪れた人と使ったお金 ----
with ui.card():
    ui.block("観光入込客数と観光消費額", "日帰りを含む実人数と、県内で使われたお金（年ごと）")
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
            ui.chart(fig)
    first = int(yr.index.min())
    ui.readout([
        f"{first}年から{iy}年にかけて、訪れた人の数は {yr.visitors[iy] / yr.visitors[first]:.2f} 倍、"
        f"使ったお金は {yr.spend[iy] / yr.spend[first]:.2f} 倍になりました。",
        f"1人あたりに直すと {per[first]:,.0f}円 → **{per[iy]:,.0f}円**。"
        + ("人数よりもお金の伸びが大きく、**1人あたりの消費が増えたことが伸びの中心**です。"
           if yr.spend[iy] / yr.spend[first] > yr.visitors[iy] / yr.visitors[first] + 0.1 else ""),
    ], source="長野県「観光入込客統計」（観光庁 共通基準）。2010〜2015年のビジネス目的、2017・2018年の入込客数は参考値")

# ---- 窓 ----
ui.group("テーマごとに詳しく見る", "知りたいことから選んでください")

grp = ir[(ir.year == iy) & (ir.period == "年計") & (ir.stay != "計") & (ir.measure != "unit_price")]
kengai = grp[(grp.purpose != "訪日外国人") & (grp.origin == "県外")].groupby("measure").value.sum() / grp.groupby("measure").value.sum()
nat = data.shukuhaku_nationality()
ny = int(nat.ym.dt.year.max())
topc = nat[nat.ym.dt.year == ny].groupby("country").value.sum().drop("その他", errors="ignore").idxmax()
fcum = s.foreign.groupby(s.index.year).cumsum()
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
    ("visitors", "01", "誰が来ている？", "県内・県外・海外、日帰りと宿泊", f"県外の人が人数の {kengai['visitors']:.0%}、使ったお金の {kengai['spend']:.0%} を占めます（{iy}年）。", "views/pref/1_visitors.py"),
    ("inbound", "02", "海外からのお客さまは？", "国・地域別、季節、全国の動き", f"{ny}年にいちばん多く泊まったのは <b>{topc}</b>。外国人の宿泊は{Y}年1〜{M}月で前年より{updown(fcum[last] / fcum[ly] - 1)}。", "views/pref/2_inbound.py"),
    ("season", "03", "いつ来ている？", "月ごとの波、日本人と外国人の違い", f"{last.year - 1}年にいちばん多かったのは <b>{full.idxmax().month}月</b>（年間の {full.max() / full.sum():.0%}）。", "views/pref/3_season.py"),
    ("stay", "04", "宿と稼働率", "宿の種類ごとの客室稼働率", f"{ym}の客室稼働率は <b>{cur.occupancy:.1f}%</b>（全国 {occ_nat:.1f}%）。", "views/pref/4_stay.py"),
    ("spend", "05", "いくら使っている？", "観光消費額と1人あたりの単価", f"{iy}年の観光消費額は <b>{yen(yr.loc[iy, 'spend'])}</b>（前年より{updown(yr.loc[iy, 'spend'] / yr.loc[iy - 1, 'spend'] - 1)}）。", "views/pref/5_spend.py"),
    ("areas", "06", "県内のどこへ？", "市町村、観光地、県内5エリア", f"観光地の延べ利用者が多いのは {'・'.join(top3)}（{ry}年）。", "views/pref/6_areas.py"),
    ("compare", "07", "他の県と比べると？", "全国の中での長野県の位置", f"延べ宿泊者数は直近12か月で <b>全国{int(rk['長野県'])}位</b>。", "views/pref/7_compare.py"),
    ("forecast", "08", "これからどうなる？", "客室稼働率の12か月先までの見通し", f"{nx.ym.year}年{nx.ym.month}月の客室稼働率は <b>{nx.pred:.0f}%前後</b> の見込み。", "views/pref/8_forecast.py"),
]
for i in range(0, len(wins), 4):
    cols = st.columns(4)
    for c, w in zip(cols, wins[i:i + 4]):
        with c:
            ui.window(*w)

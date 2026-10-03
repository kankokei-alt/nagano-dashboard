import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import data, ui

ui.setup("稼働率予測（ベータ版）", "長野県の客室稼働率が、この先どうなりそうかを月ごとに予測するページです（試作中）。")

st.warning("ベータ版です。予測モデルは統計データを取り込んだ後に学習します。いまは予測に使う「カレンダー要因」だけを表示しています。", icon="🧪")

# --- カレンダー要因（実データ: 内閣府の祝日から計算） ---
cal = data.calendar_monthly()
cal["month"] = pd.to_datetime(cal.month)
cal["m"] = cal.month.dt.month
normal = cal[(cal.month >= "2015-01-01") & (cal.month < "2026-01-01")].groupby("m").off_days.mean()
today = pd.Timestamp.today().normalize().replace(day=1)
ahead = cal[(cal.month >= today) & (cal.month < today + pd.DateOffset(months=12))].copy()
ahead["diff"] = ahead.off_days - ahead.m.map(normal)
ahead["label"] = ahead.month.dt.strftime("%Y年%-m月")

best = ahead.sort_values(["diff", "long_weekends"], ascending=False).iloc[0]
worst = ahead.sort_values(["diff", "long_weekends"]).iloc[0]
ui.insight(
    f"今後12か月では <b>{best.label}</b> が例年より休みが {best['diff']:+.1f} 日多く（3連休以上 {int(best.long_weekends)} 回）、"
    f"稼働率の追い風になりそうです。逆に <b>{worst.label}</b> は例年より {worst['diff']:+.1f} 日で、"
    "早めの販促を考える月の候補です。",
    heading="カレンダーから見た追い風・向かい風",
)

colors = ["#2a78d6" if d > 0.5 else "#e34948" if d < -0.5 else "#b5b3ad" for d in ahead["diff"]]
fig = go.Figure(
    go.Bar(
        x=ahead.label, y=ahead["diff"], marker_color=colors, marker_line_width=0,
        customdata=ahead[["off_days", "long_weekends", "max_off_run"]].values,
        hovertemplate="<b>%{x}</b><br>例年との差 %{y:+.1f} 日<br>休日 %{customdata[0]} 日"
        "／3連休以上 %{customdata[1]} 回／最長 %{customdata[2]} 連休<extra></extra>",
    )
)
fig.update_layout(
    height=340, margin={"l": 10, "r": 10, "t": 10, "b": 10},
    yaxis={"title": "例年（2015〜2025年平均）との休日数の差（日）", "zeroline": True, "zerolinecolor": "#888"},
    plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, use_container_width=True)
st.caption("青＝例年より休みが多い月、赤＝少ない月。土日・祝日・年末年始（12/29〜1/3）を休日として数えています。")

st.subheader("稼働率の予測")
ui.pending("施設タイプ別（旅館・ホテルなど）の客室稼働率の予測と、その幅", ["shukuhaku", "weather", "jnto"])

with st.expander("予測のしくみ（ベータ版の設計）"):
    st.markdown(
        """
- **予測するもの**: 長野県の客室稼働率（月次、施設タイプ別）… 観光庁「宿泊旅行統計調査」
- **使う手がかり**: 前年同月の稼働率、季節、休日数と連休の回数、積雪・気温（気象庁）、
  訪日客数の動き（JNTO）、大型イベント（善光寺御開帳・御柱祭など）、コロナ・旅行支援の期間
- **進め方**: ① 季節パターンだけの単純な予測 → ② 上の手がかりを入れた機械学習モデル。
  過去の年で「当てられたか」を検証して、①より良いときだけ②を採用します
- **見せ方**: 予測値と「このくらいの幅に収まりそう」という範囲を一緒に示します
"""
    )

ui.sources(["holidays", "events", "shukuhaku", "weather", "jnto"])

import pandas as pd
import plotly.graph_objects as go

from lib import charts, compare, data, muni, ui
from lib.charts import man

code = muni.current()
NAME = muni.name(code)
ui.setup(f"{NAME}はいつ来ている？", "月ごとの波と、その形が年によってどう変わってきたか。", kicker="市町村")
code = muni.picker("season")
cmp = muni.compare_picker(code, "season")

muni.require_digital()
v = muni.visitors()
P = muni.periods()
ly, Y = P["ly"], P["Y"]
MON = [f"{m}月" for m in range(1, 13)]
SRC = "日本観光振興協会「デジタル観光統計オープンデータ」を加工して作成"
mv = v[code] if code in v else pd.Series(float("nan"), index=v.index)  # 公表されていない市町村は空の列
cur = mv[mv.index.year == ly]
cur.index = cur.index.month
cur = cur.reindex(range(1, 13))
avg = v[v.index.year == ly].mean(axis=1)
avg.index = avg.index.month
pref = v[v.index.year == ly].sum(axis=1)
pref.index = pref.index.month
pref_sh = pref / pref.sum()

if cur.notna().sum() < 12:
    ui.insight(f"{NAME}は、{ly}年に観光来訪者数が公表されていない月があります（人数が少ない月は公表されません）。"
               "公表されている月だけを表示します。" if cur.notna().any() else
               f"{NAME}は、デジタル観光統計で観光来訪者数が公表されていません。下の観光地ごとの季節は、県の観光地利用者統計で見られます。")
else:
    peak, low = int(cur.idxmax()), int(cur.idxmin())
    ui.insight(
        f"{ly}年の{NAME}は <b>{peak}月</b> がいちばん多く（1年の {cur.max() / cur.sum():.0%}）、"
        f"<b>{low}月</b> がいちばん少ない（{cur.min() / cur.sum():.0%}）。多い月は少ない月の約 {cur.max() / max(cur.min(), 1):.1f} 倍です。"
    )

if cur.notna().any():
    # ---- 1. 月別 ----
    with ui.card():
        ui.block("月別の観光来訪者数", f"{ly}年。点線は県平均（数字のある市町村の平均）")
        fig = go.Figure(go.Bar(x=MON, y=cur.values / 1e4, name=NAME, marker_color=charts.MAIN,
                               hovertemplate=f"{NAME} %{{x}} %{{y:,.1f}}万人<extra></extra>"))
        fig.add_trace(go.Scatter(x=MON, y=avg.reindex(range(1, 13)).values / 1e4, name="県平均", mode="lines+markers",
                                 line={"color": compare.PREF_COLOR, "dash": "dot", "width": 2},
                                 hovertemplate="県平均 %{x} %{y:,.1f}万人<extra></extra>"))
        for yy in [y for y in P["full"] if y != ly][-2:]:  # 12か月そろった年がほかにもあれば重ねる
            o = mv[mv.index.year == yy]
            fig.add_trace(go.Scatter(x=[f"{d.month}月" for d in o.index], y=o.values / 1e4, name=f"{yy}年", mode="lines",
                                     line={"color": charts.CONTEXT, "width": 1.5}, hovertemplate=f"{yy}年 %{{x}} %{{y:,.1f}}万人<extra></extra>"))
        charts.layout(fig, height=330, bargap=0.25)
        fig.update_yaxes(title="万人", rangemode="tozero")
        ui.chart(fig)
        r = (cur / avg.reindex(cur.index)).dropna()
        ui.readout([
            f"いちばん多いのは **{int(cur.idxmax())}月**（{man(cur.max())}）、少ないのは **{int(cur.idxmin())}月**（{man(cur.min())}）です。",
            (f"県平均と比べていちばん多いのは {int(r.idxmax())}月（県平均の {charts.times(r.max())}）、いちばん少ないのは {int(r.idxmin())}月（{charts.times(r.min())}）です。"
             if len(r) else ""),
        ], source=SRC)

    # ---- 2. 県全体との季節の違い ----
    if cur.notna().sum() == 12:
        cur_sh = cur / cur.sum()
        with ui.card():
            ui.block("県全体と比べた季節の違い", f"{ly}年。それぞれの1年を100%とした月別の割合")
            fig = go.Figure()
            for vv, label, color in [(cur_sh, NAME, charts.MAIN), (pref_sh, "県全体", compare.PREF_COLOR)]:
                fig.add_trace(go.Bar(x=MON, y=vv.values, name=label, marker_color=color, marker_line={"color": "white", "width": 1},
                                     hovertemplate=f"{label} %{{x}}: 1年の %{{y:.1%}}<extra></extra>"))
            charts.layout(fig, height=320, barmode="group", bargap=0.2)
            fig.update_yaxes(tickformat=".0%")
            ui.chart(fig)
            diff = cur_sh - pref_sh
            w, s_ = [12, 1, 2], [7, 8]
            ui.readout([
                f"県全体と比べて特に多いのは **{int(diff.idxmax())}月**（{diff.max() * 100:+.1f}ポイント）、少ないのは **{int(diff.idxmin())}月**（{diff.min() * 100:+.1f}ポイント）です。",
                f"冬（12〜2月）の割合は {NAME} {cur_sh[w].sum():.0%}、県全体 {pref_sh[w].sum():.0%}。"
                f"夏（7〜8月）は {NAME} {cur_sh[s_].sum():.0%}、県全体 {pref_sh[s_].sum():.0%} です。",
            ], source=f"{SRC}（{ly}年。県全体は数字のある市町村の合計）")

    # ---- 3. 年×月（12か月そろった年が2つ以上あるとき） ----
    full = [y for y in P["full"] if mv[mv.index.year == y].notna().sum() == 12]
    if len(full) >= 2:
        with ui.card():
            ui.block("季節の形の移り変わり", "年（縦）×月（横）。各年の1年を100%とした割合。色が濃いほど多い")
            mon = pd.DataFrame({y: mv[mv.index.year == y].set_axis(range(1, 13)) for y in full}).T
            sh2 = mon.div(mon.sum(axis=1), axis=0)
            fig = go.Figure(go.Heatmap(
                z=sh2.values, x=MON, y=[f"{yy}年" for yy in sh2.index], colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]],
                zmin=0, text=[[f"{x:.0%}" for x in r] for r in sh2.values], texttemplate="%{text}", textfont={"size": 10}, xgap=2, ygap=2,
                hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "割合", "tickformat": ".0%"},
            ))
            charts.layout(fig, height=80 + 34 * len(sh2))
            fig.update_xaxes(side="top")
            fig.update_yaxes(autorange="reversed", showgrid=False)
            ui.chart(fig)
            peaks = sh2.idxmax(axis=1)
            ui.readout([f"いちばん多い月は、{'・'.join(f'{m}月（{(peaks == m).sum()}回）' for m in peaks.value_counts().index)} でした。"],
                       source=SRC)

# ---- 4. 観光地×月 ----
sp = data.riyousha_spots()
ry = int(sp.year.max())
s = sp[(sp.municipality_code == code) & (sp.year == ry)].dropna(subset=charts.MONTHS).sort_values("total", ascending=False)
s = s[s[charts.MONTHS].sum(axis=1) > 0]
if len(s) >= 2:
    with ui.card():
        ui.block("観光地ごとの季節", f"{ry}年。県の調査対象の観光地ごとに、1年を100%とした月別の割合")
        hm = s.set_index("spot")[charts.MONTHS]
        hm = hm.div(hm.sum(axis=1), axis=0)
        fig = go.Figure(go.Heatmap(
            z=hm.values, x=MON, y=hm.index, colorscale=[[0, "#f4f8fd"], [0.5, charts.SEQ[2]], [1, charts.SEQ[-1]]], zmin=0,
            text=[[f"{v:.0%}" for v in r] for r in hm.values], texttemplate="%{text}", textfont={"size": 10}, xgap=2, ygap=2,
            hovertemplate="%{y} %{x}: 1年の %{z:.1%}<extra></extra>", colorbar={"title": "割合", "tickformat": ".0%"},
        ))
        charts.layout(fig, height=70 + 30 * len(hm))
        fig.update_xaxes(side="top")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        ui.chart(fig)
        pk = hm.idxmax(axis=1).map(lambda k: int(k[1:]))
        ui.readout([
            "それぞれいちばん多い月: " + "、".join(f"{k} {v}月" for k, v in pk.items()) + "。",
            f"季節の差がいちばん大きいのは **{(hm.max(axis=1) - hm.min(axis=1)).idxmax()}**、1年を通して来るのは **{(hm.max(axis=1) - hm.min(axis=1)).idxmin()}** です。",
        ], source=f"長野県「観光地利用者統計調査」（{ry}年）")

ui.sources(["digital", "riyousha"])

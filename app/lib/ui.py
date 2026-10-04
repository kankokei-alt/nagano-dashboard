"""画面の共通パーツ（見出し・カード・KPI・読み取れること・データのダウンロード）。

デザインの方針: 落ち着いた紙の色の背景に白いカード。文字は BIZ UDPゴシック（読みやすさに配慮したユニバーサルデザイン書体）。
色はグラフの役割色（lib.charts）と同じ青を基調に、増減だけ緑・赤で示す。

レポート作成（views/report.py）のために「記録モード」を持つ。start_capture(リスト) のあと各ページを実行すると、
画面には出さずに、見出し・グラフ・読み取れること・出典をセクションごとに記録する。
"""
import contextlib
import inspect
import re
import threading

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import data

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&display=swap');
:root {
  /* 信州の色: アルプスの紺・空の青・りんごの赤・高原の緑・雪の白 */
  --alps: #1e3a5f; --alps-2: #2c5282; --sky: #2f6db5; --apple: #c8432f; --forest: #24936a;
  --ink: #1b2733; --muted: #5d6876; --line: #e3e1d9; --paper: #f7f6f1; --card: #ffffff;
  --accent: #2f6db5; --accent-soft: #eaf1f9; --up: #1d7a56; --up-soft: #e2f2ea; --down: #b8392a; --down-soft: #fbe8e4;
  --wrap: max(16px, calc(50vw - 580px));
}
html, body, .stApp, .stMarkdown, button, input, textarea, select, [data-testid="stWidgetLabel"] {
  font-family: "BIZ UDPGothic", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif !important;
}
.stApp {background: var(--paper); color: var(--ink);}
[data-testid="stHeader"], [data-testid="stAppDeployButton"], #MainMenu, footer {display: none !important;}
.block-container, [data-testid="stMainBlockContainer"] {padding-top: 0 !important; padding-bottom: 0 !important; max-width: 1160px;}
h1, h2, h3 {color: var(--ink); letter-spacing: .01em;}
a {color: var(--sky);}

/* 画面の端まで広げる帯（ヘッダー・ヒーロー・フッター） */
[class*="st-key-bleed"] {width: 100vw !important; max-width: 100vw; position: relative; left: 50%; margin-left: -50vw;
                         padding-left: var(--wrap) !important; padding-right: var(--wrap) !important;}

/* サイトヘッダー */
[class*="st-key-bleed_header"] {background: #fff; border-bottom: 1px solid var(--line); padding-top: .55rem; padding-bottom: .35rem;}
[data-testid="stElementContainer"]:has(style) {display: none;}  /* CSS だけの要素の余白を消す */
.logo {display: flex; align-items: center; gap: .6rem; text-decoration: none;}
.logo .name {font-size: 1.12rem; font-weight: 700; color: var(--alps); letter-spacing: .04em; line-height: 1.2;}
.logo .sub {font-size: .68rem; color: var(--muted); letter-spacing: .06em;}
[class*="st-key-gnav"] [data-testid="stPageLink"] a {padding: .35rem .2rem; border-radius: 0; justify-content: center;}
[class*="st-key-gnav"] [data-testid="stPageLink"] p {font-size: .92rem; font-weight: 700; color: var(--ink);}
[class*="st-key-gnav_on"] [data-testid="stPageLink"] a {box-shadow: inset 0 -3px 0 var(--apple);}
[class*="st-key-gnav_on"] [data-testid="stPageLink"] p {color: var(--alps);}
[class*="st-key-gnav"] [data-testid="stPageLink"] a:hover {background: #f3f1ea;}
.upd {font-size: .7rem; color: var(--muted); text-align: right; line-height: 1.35;} .upd b {color: var(--ink); font-size: .8rem;}

/* セクション内のタブ（県全体のテーマ） */
[class*="st-key-bleed_lnav"] {background: #fbfaf6; border-bottom: 1px solid var(--line); padding-top: .25rem; padding-bottom: .25rem;}
[class*="st-key-lnav"] [data-testid="stPageLink"] a {justify-content: center; padding: .3rem .1rem; border-radius: 999px;}
[class*="st-key-lnav"] [data-testid="stPageLink"] p {font-size: .8rem; color: var(--muted); white-space: nowrap;}
[class*="st-key-lnav_on"] [data-testid="stPageLink"] a {background: var(--alps);}
[class*="st-key-lnav_on"] [data-testid="stPageLink"] p {color: #fff; font-weight: 700;}
[class*="st-key-lnav_off"] [data-testid="stPageLink"] a:hover {background: #efece3;}

/* ヒーロー（扉ページ） */
[class*="st-key-bleed_hero"] {background: linear-gradient(160deg, #183150 0%, #2c5282 55%, #3d6fa5 100%); color: #fff;
                              padding-top: 2.4rem; padding-bottom: 0; overflow: hidden;}
.hero {display: flex; justify-content: space-between; align-items: flex-end; gap: 1.5rem; position: relative; z-index: 1;}
.hero .kicker {font-size: .78rem; letter-spacing: .22em; color: #cfe0f3; font-weight: 700;}
.hero .title {font-size: 2.3rem; font-weight: 700; margin: .3rem 0 .4rem; line-height: 1.3; color: #fff;}
.hero .lead {font-size: .98rem; color: #dce8f5;}
.hero .stamp {flex: 0 0 auto; text-align: right; font-size: .76rem; color: #dce8f5; border: 1px solid rgba(255,255,255,.35);
              border-radius: 12px; padding: .5rem .85rem; line-height: 1.5; background: rgba(255,255,255,.08);}
.hero .stamp b {color: #fff; font-size: .92rem;}
.ridge {display: block; width: calc(100% + 2 * var(--wrap) + 60px); margin-left: calc(-1 * var(--wrap) - 30px); height: 80px; margin-top: 1.4rem;}

/* ふつうのページの見出し */
.ph {display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin: 1.6rem 0 1rem;}
.crumb {font-size: .76rem; color: var(--muted);} .crumb b {color: var(--forest);}
.ph .title {font-size: 1.9rem; font-weight: 700; margin: .2rem 0 .3rem; line-height: 1.3; color: var(--ink);}
.ph .lead {color: var(--muted); font-size: .95rem;}
.ph .stamp {flex: 0 0 auto; text-align: right; font-size: .74rem; color: var(--muted); line-height: 1.5;}
.ph .stamp b {color: var(--ink); font-size: .86rem;}
.line-ridge {display: block; width: 180px; height: 14px; margin-top: .5rem;}

/* ここがポイント */
.insight {background: #fff; border: 1px solid var(--line); border-left: 4px solid var(--forest); border-radius: 14px;
          padding: 1.05rem 1.3rem; margin: 1.2rem 0 1.2rem;}
.insight .tag {display: inline-block; font-size: .74rem; font-weight: 700; color: var(--forest); letter-spacing: .1em; margin-bottom: .3rem;}
.insight p {margin: 0; font-size: 1.02rem; line-height: 1.85;}

/* グループ見出し（例: 2026年の状況 / 2025年の実績） */
.group {display: flex; align-items: baseline; gap: .8rem; margin: 1.9rem 0 .7rem; padding-bottom: .4rem; border-bottom: 1px solid var(--line);}
.group h2 {font-size: 1.22rem !important; font-weight: 700; margin: 0; padding: 0 !important; color: var(--alps);}
.group h2::before {content: ""; display: inline-block; width: 14px; height: 10px; margin-right: .5rem; vertical-align: 1px;
                   background: var(--apple); clip-path: polygon(50% 0, 100% 100%, 0 100%);}
.group span {font-size: .82rem; color: var(--muted);}

/* KPI */
.kpi {background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: .95rem 1.1rem; height: 100%;}
.kpi .label {font-size: .8rem; color: var(--muted);}
.kpi .value {font-size: 1.85rem; font-weight: 700; line-height: 1.35; margin: .15rem 0 .25rem; color: var(--alps);}
.kpi .row {display: flex; align-items: center; gap: .45rem; flex-wrap: wrap; font-size: .78rem; color: var(--muted);}
.badge {display: inline-block; font-size: .78rem; font-weight: 700; padding: .12rem .5rem; border-radius: 999px;}
.badge.up {background: var(--up-soft); color: var(--up);} .badge.down {background: var(--down-soft); color: var(--down);}
.badge.flat {background: #eef0f2; color: var(--muted);}

/* セクションのカード */
[class*="st-key-card"] {background: var(--card); border: 1px solid var(--line); border-radius: 16px;
                        padding: 1.3rem 1.5rem 1rem; margin-top: 1.1rem; box-shadow: 0 1px 2px rgba(16,24,40,.04);}
.blk h3 {font-size: 1.15rem; font-weight: 700; margin: 0; padding: 0; color: var(--ink);}
.blk .desc {font-size: .86rem; color: var(--muted); margin-top: .2rem;}
.ro {border-top: 1px dashed var(--line); margin-top: .4rem; padding-top: .8rem;}
.ro .tag {font-size: .74rem; font-weight: 700; color: var(--forest); letter-spacing: .1em;}
.ro ul {margin: .35rem 0 .2rem; padding-left: 1.1rem;} .ro li {font-size: .95rem; line-height: 1.75; margin: .1rem 0;}
.ro li::marker {color: var(--forest);}
.src {font-size: .76rem; color: var(--muted); margin: .3rem 0 .2rem;} .src a {color: var(--muted);}
[class*="st-key-card"] [data-testid="stExpander"] details {border: none; background: transparent;}
[class*="st-key-card"] [data-testid="stExpander"] summary {font-size: .82rem; color: var(--sky); padding-left: 0;}

/* 扉ページの窓 */
[class*="st-key-window"] {background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 1.1rem 1.2rem .8rem;
                          height: 236px !important; min-height: 236px; justify-content: space-between; flex-wrap: nowrap !important;
                          border-top: 3px solid var(--alps); transition: transform .15s, box-shadow .15s;}
[class*="st-key-window"]:hover {transform: translateY(-2px); box-shadow: 0 8px 20px rgba(30,58,95,.12);}
.wn {font-size: .72rem; font-weight: 700; color: var(--apple); letter-spacing: .12em;}
.wt {font-size: 1.08rem; font-weight: 700; margin: .15rem 0 .15rem; color: var(--alps);}
.wq {font-size: .8rem; color: var(--muted); margin-bottom: .55rem;}
.wv {font-size: .9rem; line-height: 1.6;}
[class*="st-key-window"] [data-testid="stPageLink"] a {padding-left: 0;}
[class*="st-key-window"] [data-testid="stPageLink"] p {font-weight: 700; color: var(--sky);}

/* 前後のテーマ */
[class*="st-key-pager"] [data-testid="stPageLink"] a {background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: .8rem 1rem;}
[class*="st-key-pager"] [data-testid="stPageLink"] p {font-weight: 700; color: var(--alps);}

/* フッター */
[class*="st-key-bleed_footer"] {background: var(--alps); color: #cdd8e6; margin-top: 3rem; padding-top: 0; padding-bottom: 2rem; overflow: hidden;}
.foot-ridge {display: block; width: calc(100% + 2 * var(--wrap) + 60px); margin-left: calc(-1 * var(--wrap) - 30px); height: 56px; margin-bottom: 1rem;}
.foot {display: flex; justify-content: space-between; gap: 2rem; flex-wrap: wrap; font-size: .8rem; line-height: 1.8;}
.foot .name {font-size: 1rem; font-weight: 700; color: #fff; letter-spacing: .05em;}
.foot a {color: #e4ecf6;}

.pending {border: 1px dashed var(--line); border-radius: 12px; padding: 1.2rem; color: var(--muted); text-align: center;}
</style>
"""

# あしらい: 北アルプスの稜線（左から右へ。手描きの折れ線）
RIDGE = ("M0,70 L60,52 L110,60 L170,30 L215,46 L262,20 L300,38 L345,26 L400,50 L455,34 L500,44 L560,14 L610,36 "
         "L660,28 L720,48 L780,22 L830,40 L880,32 L940,52 L1000,30 L1050,42 L1110,26 L1160,44 L1200,38")
LOGO = ('<svg width="38" height="28" viewBox="0 0 38 28" aria-hidden="true">'
        '<circle cx="29" cy="7" r="4.5" fill="#c8432f"/>'
        '<path d="M1 27 L13 9 L19 17 L24 11 L37 27 Z" fill="#1e3a5f"/>'
        '<path d="M9.7 14 L13 9 L16.2 13.6 L14.2 12.6 L12.4 14.4 Z M21.6 14 L24 11 L26.4 14.2 L24.9 13.4 Z" fill="#fff"/>'
        '<path d="M1 27 L9 21 L14 24 L20 19 L28 25 L37 27 Z" fill="#24936a"/></svg>')

_tl = threading.local()  # 利用者（セッション）ごとに別々に持つ状態。Streamlit は利用者ごとに別のスレッドで動く


def _st() -> dict:
    if not hasattr(_tl, "s"):
        _tl.s = {"capture": None, "page": {"title": "", "card": 0}, "cur": {}}
    return _tl.s


def start_capture(store: list) -> None:
    """記録モードにする（レポート作成用）。画面には出さず、セクションごとに store に記録する。"""
    _st()["capture"] = store


def stop_capture() -> None:
    _st()["capture"] = None


def _cap():
    return _st()["capture"]

# 出典の文字から、元データのページへのリンクを引く
SOURCE_LINKS = [("宿泊旅行統計", "shukuhaku"), ("観光入込客統計", "irikomi"), ("観光地利用者統計", "riyousha"),
                ("JNTO", "jnto"), ("訪日外客統計", "jnto"), ("気象庁", "weather"), ("消費者物価指数", "macro"),
                ("景気ウォッチャー", "macro"), ("国民の祝日", "holidays"), ("国土数値情報", "boundaries")]


def _md(text: str) -> str:
    """**太字** を <b> に（HTML の中で使う）。"""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


# サイトの構成（ヘッダーのメニュー・セクション内のタブ・前後のテーマ）
GNAV = [("pref", "長野県全体", "views/pref/0_top.py"), ("muni", "市町村", "views/2_municipality.py"),
        ("kouiki", "広域連携", "views/3_kouiki.py"), ("report", "レポートを作る", "views/report.py"),
        ("data", "データと出典", "views/9_data.py")]
LNAV = [("views/pref/0_top.py", "全体像"), ("views/pref/1_visitors.py", "誰が来ている"),
        ("views/pref/2_inbound.py", "海外から"), ("views/pref/3_season.py", "季節"),
        ("views/pref/4_stay.py", "宿・稼働率"), ("views/pref/5_spend.py", "消費"),
        ("views/pref/6_areas.py", "県内のエリア"), ("views/pref/7_compare.py", "他県と比べる"),
        ("views/pref/8_forecast.py", "これから")]
SECTION = {"長野県全体": "pref", "市町村": "muni", "広域連携": "kouiki", "資料室": None}


def _here() -> str:
    """呼び出したページのファイル（app/ からの相対パス）。"""
    for f in inspect.stack()[2:6]:
        if "/views/" in f.filename:
            return "views/" + f.filename.split("/views/", 1)[1]
    return ""


def _ridge(height: int, color: str, fill: str | None = None, cls: str = "ridge") -> str:
    path = RIDGE + (" L1200,90 L0,90 Z" if fill else "")
    attr = f'fill="{fill}" stroke="none"' if fill else f'fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round"'
    return (f'<svg class="{cls}" viewBox="0 0 1200 90" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="{path}" {attr}/></svg>')


def _header(here: str, sec: str | None) -> None:
    last = data.shukuhaku().index.max()
    with st.container(key="bleed_header"):
        c1, c2, c3 = st.columns([2.3, 5.2, 1.1], vertical_alignment="center")
        with c1:
            st.markdown(f'<div class="logo">{LOGO}<div><div class="name">信州 観光データ</div>'
                        f'<div class="sub">長野県 観光分析ダッシュボード</div></div></div>', unsafe_allow_html=True)
        with c2:
            cols = st.columns(len(GNAV))
            for c, (key, label, path) in zip(cols, GNAV):
                on = (key == sec) or (path == here)
                with c, st.container(key=f"gnav_{'on' if on else 'off'}_{key}"):
                    st.page_link(path, label=label)
        with c3:
            st.markdown(f'<div class="upd">データ更新<br><b>{last.year}年{last.month}月分</b></div>', unsafe_allow_html=True)
    if sec == "pref":
        with st.container(key="bleed_lnav"):
            cols = st.columns(len(LNAV))
            for i, (c, (path, label)) in enumerate(zip(cols, LNAV)):
                with c, st.container(key=f"lnav_{'on' if path == here else 'off'}_{i}"):
                    st.page_link(path, label=label)


def setup(title: str, lead: str, kicker: str = "長野県全体") -> None:
    here = _here()
    _st()["page"].update(title=title, card=0, here=here, kicker=kicker)
    if _cap() is not None:
        return
    st.markdown(CSS, unsafe_allow_html=True)
    sec = SECTION.get(kicker, "pref")
    _header(here, sec)
    last = data.shukuhaku().index.max()
    if here.endswith("0_top.py"):
        with st.container(key="bleed_hero"):
            st.markdown(
                f'<div class="hero"><div><div class="kicker">SHINSHU TOURISM DATA</div><div class="title" role="heading" aria-level="1">{title}</div>'
                f'<div class="lead">{lead}</div></div>'
                f'<div class="stamp">宿泊データ<br><b>{last.year}年{last.month}月分まで</b></div></div>'
                '<svg class="ridge" viewBox="0 0 1200 90" preserveAspectRatio="none" aria-hidden="true">'
                f'<path d="{RIDGE} L1200,90 L0,90 Z" fill="rgba(255,255,255,.16)" transform="translate(-40,-10)"/>'
                f'<path d="{RIDGE} L1200,90 L0,90 Z" fill="#f7f6f1" transform="translate(0,22)"/></svg>',
                unsafe_allow_html=True,
            )
        return
    crumb = f'<b>{kicker}</b>' + (f" ／ {title}" if kicker != title else "")
    st.markdown(
        f'<div class="ph"><div><div class="crumb">{crumb}</div><div class="title" role="heading" aria-level="1">{title}</div>'
        f'<div class="lead">{lead}</div>{_ridge(14, "#24936a", cls="line-ridge")}</div>'
        f'<div class="stamp">宿泊データ<br><b>{last.year}年{last.month}月分まで</b></div></div>',
        unsafe_allow_html=True,
    )


def footer() -> None:
    """ページの最後: 前後のテーマへの案内と、サイトのフッター（main.py から呼ぶ）。"""
    if _cap() is not None:
        return
    here = _st()["page"].get("here", "")
    paths = [p for p, _ in LNAV]
    if here in paths:
        i = paths.index(here)
        with st.container(key="pager"):
            c1, c2 = st.columns(2)
            if i > 0:
                with c1:
                    st.page_link(LNAV[i - 1][0], label=f"← 前のテーマ：{LNAV[i - 1][1]}")
            if i < len(LNAV) - 1:
                with c2:
                    st.page_link(LNAV[i + 1][0], label=f"次のテーマ：{LNAV[i + 1][1]} →")
    with st.container(key="bleed_footer"):
        st.markdown(
            '<svg class="foot-ridge" viewBox="0 0 1200 90" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="{RIDGE} L1200,0 L0,0 Z" fill="#f7f6f1" transform="translate(0,-8) scale(1,1)"/></svg>'
            '<div class="foot"><div><div class="name">信州 観光データ</div>'
            '長野県の観光を、公的統計から読み解くダッシュボード（試行版）<br>'
            '数字と文章は公表データから自動で作成しています。</div>'
            '<div>主な出典: 観光庁「宿泊旅行統計調査」、長野県「観光入込客統計」「観光地利用者統計調査」、<br>'
            '日本政府観光局（JNTO）「訪日外客統計」、気象庁「過去の気象データ」、総務省・内閣府（e-Stat）<br>'
            '詳しくは「データと出典」をご覧ください。</div></div>',
            unsafe_allow_html=True,
        )


def insight(text: str, heading: str = "ここがポイント") -> None:
    if _cap() is not None:
        _cap().append({"page": _st()["page"]["title"], "kind": "insight", "title": heading, "points": [text]})
        return
    st.markdown(f'<div class="insight"><span class="tag">{heading}</span><p>{text}</p></div>', unsafe_allow_html=True)


def group(title: str, note: str = "") -> None:
    """KPIなどのまとまりに付ける見出し（例: 2026年の状況）。"""
    if _cap() is None:
        st.markdown(f'<div class="group"><h2>{title}</h2><span>{note}</span></div>', unsafe_allow_html=True)


def badge(x: float | None, kind: str = "pct") -> str:
    """増減のバッジ。kind='pct' は比率、'pt' はポイント差。"""
    if x is None or pd.isna(x):
        return ""
    small = 0.005 if kind == "pct" else 0.05
    cls = "flat" if abs(x) < small else "up" if x > 0 else "down"
    arrow = "→" if cls == "flat" else "▲" if x > 0 else "▼"
    txt = f"{x:+.1%}" if kind == "pct" else f"{x:+.1f}pt"
    return f'<span class="badge {cls}">{arrow} {txt}</span>'


def kpi(label: str, value: str | None, sub: str = "", delta: float | None = None, delta_kind: str = "pct") -> None:
    if _cap() is not None:
        return
    v = value if value is not None else "—"
    s = sub if value is not None else "データ準備中"
    st.markdown(
        f'<div class="kpi"><div class="label">{label}</div><div class="value">{v}</div>'
        f'<div class="row">{badge(delta, delta_kind)}<span>{s}</span></div></div>',
        unsafe_allow_html=True,
    )


def card():
    """セクションを白いカードで囲む。with ui.card(): の中に見出し・グラフ・読み取れることを置く。"""
    _st()["page"]["card"] += 1
    if _cap() is not None:
        return contextlib.nullcontext()
    return st.container(key=f"card_{_st()['page']['card']}")


def block(title: str, desc: str = "") -> None:
    """グラフの見出し。端的なタイトルと、その下に1行の説明。"""
    cur = _st()["cur"] = {}
    cur.update(page=_st()["page"]["title"], kind="section", title=title, desc=desc, figs=[], points=[], source="")
    if _cap() is not None:
        _cap().append(cur)
        return
    st.markdown(f'<div class="blk"><h3>{title}</h3>' + (f'<div class="desc">{desc}</div>' if desc else "") + "</div>",
                unsafe_allow_html=True)


def chart(fig: go.Figure, **kw) -> None:
    """グラフを出す（記録モードでは記録だけ）。"""
    fig.update_layout(font={"family": 'BIZ UDPGothic, "Hiragino Sans", Meiryo, sans-serif', "color": "#1d2733"})
    cur = _st()["cur"]
    if cur:
        cur["figs"].append(fig)
    if _cap() is not None:
        return
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "toImageButtonOptions": {"scale": 2}})


def _links(source: str) -> list[tuple[str, str]]:
    ds = data.datasets().set_index("id")
    seen, out = set(), []
    for word, i in SOURCE_LINKS:
        if word in source and i not in seen and i in ds.index and isinstance(ds.loc[i, "url"], str):
            seen.add(i)
            out.append((ds.loc[i, "name"], ds.loc[i, "url"]))
    return out


def fig_table(fig: go.Figure) -> pd.DataFrame:
    """グラフに描いた数値を表にする（「数値を見る」とCSVダウンロード用）。"""
    titles = [a.text for a in (fig.layout.annotations or [])]  # 小さなグラフを並べたとき、先頭から各グラフの題名
    frames = []
    for tr in fig.data:
        if getattr(tr, "fill", None) == "toself" or getattr(tr, "hoverinfo", None) == "skip":
            continue
        name = tr.name or ""
        if not name and getattr(tr, "xaxis", None) and tr.xaxis not in ("x", "x1"):
            k = int(tr.xaxis[1:]) - 1
            name = re.sub(r"<[^>]+>", "", titles[k]) if k < len(titles) else ""
        if tr.type == "heatmap":
            df = pd.DataFrame(tr.z, index=list(tr.y), columns=list(tr.x))
            frames.append(df.reset_index(names="項目").melt(id_vars="項目", var_name="区分", value_name="値").assign(系列=name))
            continue
        if tr.type not in ("bar", "scatter") or tr.x is None or tr.y is None:
            continue
        cat, val = (tr.y, tr.x) if getattr(tr, "orientation", None) == "h" else (tr.x, tr.y)
        frames.append(pd.DataFrame({"系列": name, "項目": list(cat), "値": list(val)}))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "区分" in df:
        return df[["系列", "項目", "区分", "値"]] if df.系列.nunique() > 1 else df[["項目", "区分", "値"]]
    if pd.api.types.is_datetime64_any_dtype(df["項目"]) or isinstance(df["項目"].iloc[0], pd.Timestamp):
        df["項目"] = pd.to_datetime(df["項目"]).dt.strftime("%Y-%m")
    if df.系列.nunique() > 1 and not df.duplicated(["系列", "項目"]).any():
        return df.pivot_table(index="項目", columns="系列", values="値", sort=False, aggfunc="first").reset_index()
    return df if df.系列.nunique() > 1 else df[["項目", "値"]]


def readout(points: list[str], source: str = "") -> None:
    """グラフの下の「読み取れること」と出典・数値のダウンロード。文章はデータから組み立てたものを渡す。"""
    pts = [p for p in points if p]
    cur = _st()["cur"]
    if cur:
        cur["points"] = pts
        cur["source"] = source
    if _cap() is not None:
        return
    items = "".join(f"<li>{_md(p)}</li>" for p in pts)
    st.markdown(f'<div class="ro"><span class="tag">読み取れること</span><ul>{items}</ul></div>', unsafe_allow_html=True)
    links = _links(source)
    if source:
        link_html = "".join(f' ・<a href="{u}" target="_blank">{n}の公表ページ ↗</a>' for n, u in links)
        st.markdown(f'<div class="src">出典: {source}{link_html}</div>', unsafe_allow_html=True)
    figs = cur.get("figs", [])
    tables = [t for t in (fig_table(f) for f in figs) if not t.empty]
    if tables:
        with st.expander("数値を見る・ダウンロード"):
            for i, t in enumerate(tables):
                st.dataframe(t, hide_index=True, use_container_width=True, height=min(38 * (len(t) + 1), 320))
                name = re.sub(r"[^\w一-龥ぁ-んァ-ン]", "", cur.get("title", "data"))[:30] or "data"
                st.download_button("CSVでダウンロード", t.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"{name}{'_' + str(i + 1) if len(tables) > 1 else ''}.csv", mime="text/csv",
                                   key=f"dl_{_st()['page']['title']}_{_st()['page']['card']}_{i}")


def window(key: str, num: str, title: str, question: str, teaser: str, page: str) -> None:
    """扉ページの「窓」。押すと詳細ページへ移る。"""
    if _cap() is not None:
        return
    with st.container(key=f"window_{key}"):
        st.markdown(f'<div class="wn">{num}</div><div class="wt">{title}</div><div class="wq">{question}</div>'
                    f'<div class="wv">{teaser}</div>', unsafe_allow_html=True)
        st.page_link(page, label="詳しく見る →")


def pending(what: str, dataset_ids: list[str]) -> None:
    if _cap() is not None:
        return
    ds = data.datasets().set_index("id")
    names = "、".join(ds.loc[i, "name"] for i in dataset_ids if i in ds.index)
    st.markdown(f'<div class="pending"><b>{what}</b><br><small>使うデータ: {names}（取得準備中）</small></div>',
                unsafe_allow_html=True)


def sources(dataset_ids: list[str]) -> None:
    if _cap() is not None:
        return
    ds = data.datasets().set_index("id")
    with st.expander("このページで使っているデータ"):
        for i in dataset_ids:
            r = ds.loc[i]
            link = f" ［[公表ページ ↗]({r['url']})］" if isinstance(r["url"], str) else ""
            st.markdown(f"- **{r['name']}**（{r['provider']}）… {r['status']}{link}")

"""画面の共通パーツ（見出し・カード・KPI・読み取れること・データのダウンロード）。

デザインの方針: 落ち着いた紙の色の背景に白いカード。文字は BIZ UDPゴシック（読みやすさに配慮したユニバーサルデザイン書体）。
色はグラフの役割色（lib.charts）と同じ青を基調に、増減だけ緑・赤で示す。

レポート作成（views/report.py）のために「記録モード」を持つ。start_capture(リスト) のあと各ページを実行すると、
画面には出さずに、見出し・グラフ・読み取れること・出典をセクションごとに記録する。
"""
import contextlib
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
  --ink: #1d2733; --muted: #5f6b7a; --line: #e4e2db; --paper: #f6f5f1; --card: #ffffff;
  --accent: #1f5fa8; --accent-soft: #e9f0f8; --up: #17805a; --up-soft: #e3f3ec; --down: #c0392b; --down-soft: #fbe9e6;
}
html, body, .stApp, .stMarkdown, button, input, textarea, select, [data-testid="stWidgetLabel"] {
  font-family: "BIZ UDPGothic", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif !important;
}
.stApp {background: var(--paper); color: var(--ink);}
.block-container, [data-testid="stMainBlockContainer"] {padding-top: 4.6rem !important; padding-bottom: 4rem; max-width: 1160px;}
[data-testid="stAppDeployButton"], #MainMenu, footer {display: none !important;}
h1, h2, h3 {color: var(--ink); letter-spacing: .01em;}

/* ページの見出し */
.ph {display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin: .2rem 0 1.2rem;}
.ph .kicker {font-size: .8rem; font-weight: 700; color: var(--accent); letter-spacing: .08em;}
.ph .title {font-size: 2rem; font-weight: 700; margin: .15rem 0 .3rem; line-height: 1.3; color: var(--ink);}
.ph .lead {color: var(--muted); font-size: .95rem;}
.ph .stamp {flex: 0 0 auto; text-align: right; font-size: .78rem; color: var(--muted); border: 1px solid var(--line);
            background: var(--card); border-radius: 10px; padding: .45rem .8rem; line-height: 1.5;}
.ph .stamp b {color: var(--ink); font-size: .9rem;}

/* ここがポイント */
.insight {background: var(--accent-soft); border-radius: 14px; padding: 1.1rem 1.3rem; margin: 0 0 1.4rem;}
.insight .tag {display: inline-block; font-size: .75rem; font-weight: 700; color: var(--accent); letter-spacing: .06em; margin-bottom: .35rem;}
.insight p {margin: 0; font-size: 1.02rem; line-height: 1.8;}

/* グループ見出し（例: 2026年の状況 / 2025年の実績） */
.group {display: flex; align-items: baseline; gap: .7rem; margin: 1.6rem 0 .6rem;}
.group h2 {font-size: 1.25rem !important; font-weight: 700; margin: 0; padding: 0 !important;}
.group span {font-size: .82rem; color: var(--muted);}

/* KPI */
.kpi {background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: .95rem 1.1rem; height: 100%;}
.kpi .label {font-size: .8rem; color: var(--muted);}
.kpi .value {font-size: 1.85rem; font-weight: 700; line-height: 1.35; margin: .15rem 0 .25rem; color: var(--ink);}
.kpi .row {display: flex; align-items: center; gap: .45rem; flex-wrap: wrap; font-size: .78rem; color: var(--muted);}
.badge {display: inline-block; font-size: .78rem; font-weight: 700; padding: .12rem .5rem; border-radius: 999px;}
.badge.up {background: var(--up-soft); color: var(--up);} .badge.down {background: var(--down-soft); color: var(--down);}
.badge.flat {background: #eef0f2; color: var(--muted);}

/* セクションのカード */
[class*="st-key-card"] {background: var(--card); border: 1px solid var(--line); border-radius: 16px;
                        padding: 1.3rem 1.5rem 1rem; margin-top: 1.1rem; box-shadow: 0 1px 2px rgba(16,24,40,.04);}
.blk h3 {font-size: 1.15rem; font-weight: 700; margin: 0; padding: 0;}
.blk .desc {font-size: .86rem; color: var(--muted); margin-top: .2rem;}
.ro {border-top: 1px solid var(--line); margin-top: .4rem; padding-top: .8rem;}
.ro .tag {font-size: .74rem; font-weight: 700; color: var(--muted); letter-spacing: .08em;}
.ro ul {margin: .35rem 0 .2rem; padding-left: 1.1rem;} .ro li {font-size: .95rem; line-height: 1.75; margin: .1rem 0;}
.src {font-size: .76rem; color: var(--muted); margin: .3rem 0 .2rem;} .src a {color: var(--muted);}
[class*="st-key-card"] [data-testid="stExpander"] details {border: none; background: transparent;}
[class*="st-key-card"] [data-testid="stExpander"] summary {font-size: .82rem; color: var(--accent); padding-left: 0;}

/* 扉ページの窓 */
[class*="st-key-window"] {background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 1.1rem 1.2rem .8rem;
                          height: 236px !important; min-height: 236px; justify-content: space-between; flex-wrap: nowrap !important;
                          transition: border-color .15s, box-shadow .15s;}
[class*="st-key-window"]:hover {border-color: var(--accent); box-shadow: 0 4px 14px rgba(31,95,168,.10);}
.wn {font-size: .72rem; font-weight: 700; color: var(--accent); letter-spacing: .1em;}
.wt {font-size: 1.08rem; font-weight: 700; margin: .15rem 0 .15rem;}
.wq {font-size: .8rem; color: var(--muted); margin-bottom: .55rem;}
.wv {font-size: .9rem; line-height: 1.6;}
[class*="st-key-window"] [data-testid="stPageLink"] a {padding-left: 0;}
[class*="st-key-window"] [data-testid="stPageLink"] p {font-weight: 700; color: var(--accent);}

.pending {border: 1px dashed var(--line); border-radius: 12px; padding: 1.2rem; color: var(--muted); text-align: center;}
</style>
"""

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


def setup(title: str, lead: str, kicker: str = "長野県全体") -> None:
    _st()["page"].update(title=title, card=0)
    if _cap() is not None:
        return
    st.markdown(CSS, unsafe_allow_html=True)
    s = data.shukuhaku()
    last = s.index.max()
    st.markdown(
        f'<div class="ph"><div><div class="kicker">{kicker}</div><div class="title" role="heading" aria-level="1">{title}</div><div class="lead">{lead}</div></div>'
        f'<div class="stamp">宿泊データ<br><b>{last.year}年{last.month}月分まで</b></div></div>',
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

"""レポートを作る: 各ページのグラフから必要なものを選んで、1つのレポート（HTML）にまとめる。

各ページを「記録モード」（lib.ui.start_capture）で実行し、画面には出さずに見出し・グラフ・読み取れること・出典を集める。
ページのコードは画面と同じものを使うので、レポートの数字と文章はいつも画面と一致する。
レポートはグラフを動かせる HTML で、ブラウザの「印刷」から PDF にも保存できる。
"""
import datetime
import html
import re
from pathlib import Path

import plotly.graph_objects as go
import plotly.offline
import streamlit as st
import streamlit.components.v1 as components

from lib import data, ui

APP = Path(__file__).resolve().parents[1]
PAGES = [  # (ファイル, ページ名)
    ("views/pref/0_top.py", "長野県の全体像"), ("views/pref/1_visitors.py", "誰が来ている？"),
    ("views/pref/2_inbound.py", "海外からのお客さま"), ("views/pref/3_season.py", "いつ来ている？"),
    ("views/pref/4_stay.py", "宿と稼働率"), ("views/pref/5_spend.py", "いくら使っている？"),
    ("views/pref/6_areas.py", "県内のどこへ？"), ("views/pref/7_compare.py", "他の県と比べる"),
    ("views/pref/8_forecast.py", "これからの見通し（ベータ版）"),
]


class _Ctx:
    """何もしない部品（with にも使える）。"""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return lambda *a, **k: _Ctx()

    def __call__(self, *a, **k):
        return _Ctx()


class _QuietSt(_Ctx):
    """記録モードでページを実行するときの st の代わり。入力部品は初期値を返す。"""

    def columns(self, spec, **k):
        return [_Ctx() for _ in range(spec if isinstance(spec, int) else len(spec))]

    def tabs(self, labels, **k):
        return [_Ctx() for _ in labels]

    def radio(self, label, options, index=0, **k):
        o = list(options)
        return o[index] if o else None

    selectbox = radio

    def multiselect(self, label, options, default=None, **k):
        return list(default or [])

    def select_slider(self, label, options=(), value=None, **k):
        o = list(options)
        return value if value is not None else (o[0] if o else None)

    def slider(self, label, min_value=None, max_value=None, value=None, **k):
        return value

    def checkbox(self, label, value=False, **k):
        return value

    toggle = checkbox


@st.cache_resource(ttl=3600, show_spinner="グラフを集めています…")
def collect() -> list[dict]:
    out: list[dict] = []
    for path, name in PAGES:
        src = (APP / path).read_text(encoding="utf-8").replace("import streamlit as st", "st = __st__")
        ui.start_capture(out)
        try:
            exec(compile(src, path, "exec"), {"__st__": _QuietSt(), "__name__": "__report__"})
        except Exception as e:  # 1ページの失敗でレポート全体を止めない
            out.append({"page": name, "kind": "error", "title": f"{name} を読み込めませんでした（{type(e).__name__}）", "figs": []})
        finally:
            ui.stop_capture()
    return out


def _for_report(fig):
    """画面用のグラフを、単独の HTML でも軸の文字が切れないように整える（元のグラフは変えない）。"""
    f = go.Figure(fig)
    f.update_layout(template="plotly_white", margin={"l": 70, "r": 30, "t": 50, "b": 60},
                    paper_bgcolor="white", plot_bgcolor="white")
    f.update_xaxes(automargin=True)
    f.update_yaxes(automargin=True)
    return f


def _md(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def build_html(title: str, intro: str, items: list[dict], inline_js: bool) -> str:
    s = data.shukuhaku()
    last = s.index.max()
    js = (f"<script>{plotly.offline.get_plotlyjs()}</script>" if inline_js
          else '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>')
    body, srcs = [], []
    page = None
    for it in items:
        if it["page"] != page:
            page = it["page"]
            body.append(f'<h2 class="pg">{html.escape(page)}</h2>')
        if it["kind"] == "insight":
            body.append(f'<div class="insight"><span>ここがポイント</span><p>{it["points"][0]}</p></div>')
            continue
        figs = "".join(_for_report(f).to_html(full_html=False, include_plotlyjs=False,
                                              config={"displaylogo": False, "responsive": True})
                       for f in it["figs"])
        pts = "".join(f"<li>{_md(p)}</li>" for p in it.get("points", []))
        if it.get("source"):
            srcs.append(it["source"])
        body.append(
            f'<section><h3>{html.escape(it["title"])}</h3><div class="desc">{html.escape(it.get("desc", ""))}</div>'
            f'<div class="figs">{figs}</div>'
            + (f'<div class="ro"><span>読み取れること</span><ul>{pts}</ul></div>' if pts else "")
            + (f'<div class="src">出典: {html.escape(it["source"])}</div>' if it.get("source") else "") + "</section>"
        )
    uniq = list(dict.fromkeys(srcs))
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>{js}
<style>
body {{font-family: "BIZ UDPGothic","Hiragino Sans","Meiryo",sans-serif; color:#1d2733; background:#f6f5f1; margin:0;}}
main {{max-width: 980px; margin: 0 auto; padding: 32px 24px 60px;}}
header {{border-bottom: 2px solid #1d2733; padding-bottom: 14px; margin-bottom: 18px;}}
header .k {{font-size: 12px; color:#1e3a5f; font-weight:700; letter-spacing:.08em;}}
header h1 {{font-size: 26px; margin: 4px 0 6px;}} header .m {{font-size: 12px; color:#5f6b7a;}}
.intro {{background:#fff; border:1px solid #e4e2db; border-radius:12px; padding:14px 18px; line-height:1.8; white-space:pre-wrap;}}
h2.pg {{font-size: 18px; margin: 28px 0 8px; color:#1e3a5f;}}
section, .insight {{background:#fff; border:1px solid #e4e2db; border-radius:14px; padding:18px 20px 12px; margin: 12px 0; break-inside: avoid;}}
.insight {{background:#eaf1f9; border:none;}} .insight span, .ro span {{font-size:11px; font-weight:700; letter-spacing:.08em; color:#1e3a5f;}}
.insight p {{margin:.3em 0 0; line-height:1.8;}}
h3 {{font-size: 16px; margin: 0;}} .desc {{font-size: 12px; color:#5f6b7a; margin-top:3px;}}
.ro {{border-top:1px solid #e4e2db; margin-top:6px; padding-top:8px;}} .ro span {{color:#5f6b7a;}}
.ro li {{font-size: 14px; line-height: 1.75;}} .src {{font-size: 11px; color:#5f6b7a;}}
footer {{margin-top: 30px; font-size: 11px; color:#5f6b7a; line-height:1.7;}}
@media print {{ body {{background:#fff;}} main {{padding: 0;}} section, .insight {{border-color:#ccc;}} @page {{size: A4; margin: 14mm;}} }}
</style></head><body><main>
<header><div class="k">長野県 観光データ レポート</div><h1>{html.escape(title)}</h1>
<div class="m">作成日 {datetime.date.today():%Y年%-m月%-d日} ／ 宿泊データ {last.year}年{last.month}月分まで</div></header>
{f'<div class="intro">{html.escape(intro)}</div>' if intro.strip() else ''}
{''.join(body)}
<footer>出典（このレポートで使った統計）<br>{'<br>'.join(html.escape(u) for u in uniq)}<br>
数値と文章は公表データから自動で作成しています。</footer>
</main></body></html>"""


ui.setup("レポートを作る", "必要なグラフを選んで、1つのレポートにまとめます。会議資料や共有にどうぞ。", kicker="資料室")

items = collect()
sections = [it for it in items if it["kind"] == "section" and it["figs"]]
insights = {it["page"]: it for it in items if it["kind"] == "insight"}
errors = [it for it in items if it["kind"] == "error"]
for e in errors:
    st.warning(e["title"])

if "picked" not in st.session_state:
    st.session_state.picked = set()

c1, c2 = st.columns([2, 1])
with c1:
    title = st.text_input("レポートの題名", value=f"長野県の観光の動向（{datetime.date.today():%Y年%-m月}）")
    intro = st.text_area("はじめに（任意）", placeholder="例: ○○会議 資料。今年の宿泊の進み具合と、インバウンドの状況をまとめました。", height=90)
with c2:
    with_insight = st.checkbox("各ページの「ここがポイント」も入れる", value=True)
    b1, b2 = st.columns(2)
    if b1.button("すべて選ぶ", use_container_width=True):
        st.session_state.picked = {i for i, _ in enumerate(sections)}
    if b2.button("選択を外す", use_container_width=True):
        st.session_state.picked = set()

st.markdown('<div class="group"><h2>入れるグラフを選ぶ</h2><span>ページごとに並んでいます</span></div>', unsafe_allow_html=True)
pages = list(dict.fromkeys(s["page"] for s in sections))
cols = st.columns(3)
for n, pg in enumerate(pages):
    with cols[n % 3]:
        with st.container(key=f"card_pick_{n}"):
            st.markdown(f"**{pg}**")
            for i, sec in enumerate(sections):
                if sec["page"] != pg:
                    continue
                on = st.checkbox(sec["title"], value=i in st.session_state.picked, key=f"pick_{i}_{len(st.session_state.picked)}",
                                 help=sec.get("desc") or None)
                (st.session_state.picked.add if on else st.session_state.picked.discard)(i)

chosen = [sections[i] for i in sorted(st.session_state.picked)]
st.markdown(f'<div class="group"><h2>レポート</h2><span>{len(chosen)} 個のグラフを選んでいます</span></div>', unsafe_allow_html=True)
if not chosen:
    st.info("上から、レポートに入れたいグラフにチェックを入れてください。")
else:
    ordered = []
    for pg in pages:
        secs = [c for c in chosen if c["page"] == pg]
        if secs and with_insight and pg in insights:
            ordered.append(insights[pg])
        ordered += secs
    report = build_html(title, intro, ordered, inline_js=True)
    st.download_button("レポートをダウンロード（HTML）", report.encode("utf-8"), file_name=f"{title}.html", mime="text/html",
                       type="primary", use_container_width=True)
    st.caption("ダウンロードしたファイルはブラウザで開けます（インターネットにつながっていなくても表示できます）。"
               "PDF にするときは、開いたあとブラウザの「印刷」から「PDF に保存」を選んでください。")
    with st.expander("プレビュー", expanded=True):
        components.html(report, height=900, scrolling=True)

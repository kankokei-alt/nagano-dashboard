"""比べる機能（市町村・広域のページで共通）。

ページ上部の「比べる」欄で、比べたい市町村をチェックボックスで選び、県平均を表示するか決める。
選んだ内容はページをまたいで覚えておき、各ページの「比べる」カードのグラフに重ねて描く。
色は、見ている市町村が信州の空（MAIN）、比べる市町村は順に別の色、県平均は灰色の点線。
"""
from dataclasses import dataclass, field

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import charts, ui

MAX = 5
PALETTE = [charts.SECOND, charts.THIRD, "#c98a12", "#7a55a8", "#1c97a8"]
PREF_COLOR = "#6f6d66"
SEL = "cmp_sel"
PREF = "cmp_pref"


@dataclass
class Sel:
    me: str
    me_name: str
    codes: list = field(default_factory=list)   # 比べる市町村（me は含まない）
    names: dict = field(default_factory=dict)
    pref: bool = True
    pref_label: str = "県平均"

    @property
    def all(self) -> list:
        return [self.me] + self.codes

    def color(self, code: str) -> str:
        return charts.MAIN if code == self.me else PALETTE[self.codes.index(code) % len(PALETTE)]

    def label(self, code: str) -> str:
        return self.names.get(code, code)


def _state(key):
    st.session_state.setdefault(key, [])
    st.session_state.setdefault(PREF, True)


def picker(me: str, master: pd.DataFrame, page: str, unit: str = "市町村") -> Sel:
    """比べる市町村を選ぶ欄。master は index=コード、列に name・kouiki。"""
    SK = f"{SEL}_{unit}"  # 市町村と広域で別々に覚える
    _state(SK)
    sel = [c for c in st.session_state[SK] if c != me and c in master.index]

    def _toggle(c):
        cur = st.session_state[SK]
        st.session_state[SK] = [x for x in cur if x != c] if c in cur else cur + [c]

    def _pref():
        st.session_state[PREF] = st.session_state[f"cmp_pref_{page}"]

    def _clear():
        st.session_state[SK] = []

    with st.container(key="cmpbar"):
        c1, c2, c3 = st.columns([1.1, 4.2, 1.3], vertical_alignment="center")
        with c1:
            st.markdown('<div class="cmplabel">比べる</div>', unsafe_allow_html=True)
        with c2:
            chips = "".join(f'<span class="chip" style="--c:{PALETTE[i % len(PALETTE)]}">{master.loc[c, "name"]}</span>'
                            for i, c in enumerate(sel))
            st.markdown(f'<div class="chips">{chips or "<span class=hint>比べる" + unit + "を選ぶと、各グラフに重ねて表示します</span>"}</div>',
                        unsafe_allow_html=True)
        with c3:
            st.checkbox("県平均", value=st.session_state[PREF], key=f"cmp_pref_{page}", on_change=_pref)
        with st.expander(f"比べる{unit}を選ぶ（{MAX}つまで）", expanded=False):
            full = len(sel) >= MAX
            for k, grp in master.groupby("kouiki", sort=False):
                st.markdown(f'<div class="cmpk">{k}</div>', unsafe_allow_html=True)
                with st.container(horizontal=True, gap="small"):
                    for c, r in grp.iterrows():
                        if c == me:
                            continue
                        on = c in sel
                        st.checkbox(r["name"], value=on, key=f"cmp_{page}_{c}", on_change=_toggle, args=(c,),
                                    disabled=full and not on)
            if sel:
                st.button("選んだものをすべて外す", key=f"cmp_clear_{page}", on_click=_clear)
    return Sel(me=me, me_name=master.loc[me, "name"], codes=sel, names=master.name.to_dict(), pref=st.session_state[PREF])


# ---------- グラフ ----------

def bars(s: Sel, values: pd.Series, pref_value=None, fmt=lambda v: f"{v:,.0f}", title: str = "", height=None,
         tickformat=None, pref_label=None) -> go.Figure:
    """見ている市町村・比べる市町村・県平均の横棒。values は index=コード。"""
    pl = pref_label or s.pref_label
    rows = [(s.label(c), values.get(c), s.color(c)) for c in s.all]
    if s.pref and pref_value is not None:
        rows.append((pl, pref_value, PREF_COLOR))
    rows = [r for r in rows if r[1] is not None and pd.notna(r[1])]
    fig = go.Figure(go.Bar(
        y=[r[0] for r in rows], x=[r[1] for r in rows], orientation="h", marker_color=[r[2] for r in rows],
        marker_pattern_shape=["/" if r[0] == pl else "" for r in rows],
        text=[fmt(r[1]) for r in rows], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    vmax = max([abs(r[1]) for r in rows] + [0])
    vmin = min([r[1] for r in rows] + [0])
    charts.layout(fig, height=height or max(200, 40 * len(rows) + 70),
                  **({"title": {"text": title, "font": {"size": 14}}} if title else {}))
    fig.update_xaxes(range=[vmin * 1.45 if vmin < 0 else 0, vmax * 1.4 or 1], tickformat=tickformat,
                     zeroline=bool(vmin < 0), zerolinecolor="rgba(128,128,128,.6)")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


def lines(s: Sel, df: pd.DataFrame, pref=None, x_title=None, y_title=None, hover="%{y:,.0f}", height=340,
          end_labels=True, pref_label=None) -> go.Figure:
    """df は index=x、列=コード。pref は県平均の Series（同じ index）。"""
    fig = go.Figure()
    ends = {}
    series = [(c, df[c].dropna(), s.color(c), 3.5 if c == s.me else 2.2, "solid") for c in s.all if c in df]
    if s.pref and pref is not None:
        series.append(("pref", pref.dropna(), PREF_COLOR, 2, "dot"))
    for c, v, color, w, dash in series:
        if v.empty:
            continue
        name = (pref_label or s.pref_label) if c == "pref" else s.label(c)
        fig.add_trace(go.Scatter(x=v.index, y=v.values, name=name, mode="lines+markers" if len(v) < 30 else "lines",
                                 line={"color": color, "width": w, "dash": dash}, marker={"size": 6},
                                 hovertemplate=f"{name} {hover}<extra></extra>"))
        ends[name] = (v.index[-1], v.iloc[-1], color)
    if end_labels and len(ends) > 1:
        span = max(abs(e[1]) for e in ends.values()) or 1
        ys = charts.spread({k: e[1] for k, e in ends.items()}, gap=span * 0.07)
        for k, (x, _, color) in ends.items():
            fig.add_annotation(x=x, y=ys[k], text=k, showarrow=False, xanchor="left", xshift=8,
                               font={"size": 11, "color": color})
    charts.layout(fig, height=height, hovermode="x unified")
    fig.update_layout(margin={"r": 90})
    if x_title:
        fig.update_xaxes(title=x_title)
    if y_title:
        fig.update_yaxes(title=y_title)
    return fig


def readout(s: Sel, values: pd.Series, pref_value=None, what: str = "", fmt=lambda v: f"{v:,.0f}",
            higher: str = "高い", lower: str = "低い", pref_label=None) -> list:
    """比べた結果の文章（いちばん高い・低い、県平均との差）。"""
    v = values.reindex(s.all).dropna()
    pl = pref_label or s.pref_label
    pts = []
    if s.me in v.index and s.pref and pref_value is not None and pd.notna(pref_value):
        me = v[s.me]
        if fmt(me) == fmt(pref_value):
            pts.append(f"{s.me_name}の{what}は {fmt(me)} で、{pl}と同じくらいです。")
        else:
            pts.append(f"{s.me_name}の{what}は {fmt(me)} で、{pl}（{fmt(pref_value)}）を{'上回って' if me > pref_value else '下回って'}います。")
    if len(v) >= 2:
        top, bot = v.idxmax(), v.idxmin()
        pts.append(f"選んだ中で{what}がいちばん{higher}のは **{s.label(top)}**（{fmt(v[top])}）、"
                   f"いちばん{lower}のは **{s.label(bot)}**（{fmt(v[bot])}）です。")
    return pts


def hint(s: Sel, unit: str = "市町村"):
    if not s.codes:
        st.caption(f"ページ上部の「比べる」で{unit}を選ぶと、ここに重ねて表示します。")

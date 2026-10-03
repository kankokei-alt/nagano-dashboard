"""見る人の負担を減らすための共通パーツ（インサイト、KPIカード、準備中表示）。"""
import streamlit as st

from . import data

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.insight {border-left: 6px solid #2a78d6; background: rgba(42,120,214,.08);
          padding: .9rem 1.1rem; border-radius: 6px; margin: .4rem 0 1.2rem;}
.insight h4 {margin: 0 0 .3rem; font-size: 1rem;}
.insight p {margin: 0; font-size: 1.05rem; line-height: 1.6;}
.kpi {border: 1px solid rgba(128,128,128,.25); border-radius: 10px; padding: .8rem 1rem; height: 100%;}
.kpi .label {font-size: .85rem; opacity: .75;}
.kpi .value {font-size: 1.9rem; font-weight: 700; line-height: 1.3;}
.kpi .sub {font-size: .8rem; opacity: .7;}
.pending {border: 1px dashed rgba(128,128,128,.5); border-radius: 10px;
          padding: 1.2rem; opacity: .85; text-align: center;}
.blk {margin: 2.2rem 0 .4rem; padding-top: 1rem; border-top: 1px solid rgba(128,128,128,.25);}
.blk h3 {margin: 0 0 .5rem; font-size: 1.35rem;}
.blk h3 {margin-bottom: .15rem;}
.blk .desc {font-size: .92rem; opacity: .7;}
[class*="st-key-readout"] {background: rgba(27,175,122,.07); border-left: 5px solid #1baf7a;
                           border-radius: 6px; padding: .7rem 1rem .4rem;}
[class*="st-key-readout"] p, [class*="st-key-readout"] li {font-size: 1rem; line-height: 1.65;}
[class*="st-key-window"] {border: 1px solid rgba(128,128,128,.3); border-radius: 12px; padding: 1rem 1.1rem;
                          height: 100%; background: rgba(128,128,128,.03);}
[class*="st-key-window"] .wt {font-size: 1.15rem; font-weight: 700; margin-bottom: .2rem;}
[class*="st-key-window"] .wq {font-size: .88rem; opacity: .75; margin-bottom: .5rem;}
[class*="st-key-window"] .wv {font-size: 1rem; line-height: 1.5; min-height: 3em;}
</style>
"""


_n = {"readout": 0}


def block(title: str, desc: str = "") -> None:
    """グラフの見出し。端的なタイトルと、その下に1行の説明。"""
    st.markdown(f'<div class="blk"><h3>{title}</h3>' + (f'<div class="desc">{desc}</div>' if desc else "") + "</div>",
                unsafe_allow_html=True)


def readout(points: list[str], source: str = "") -> None:
    """グラフの下に置く「ここから読めること」。文章はデータから組み立てたものを渡す。"""
    _n["readout"] += 1
    with st.container(key=f"readout_{_n['readout']}"):
        st.markdown("**📝 ここから読めること**\n" + "\n".join(f"- {p}" for p in points if p))
    if source:
        st.caption(f"出典: {source}")


def window(key: str, icon: str, title: str, question: str, teaser: str, page: str) -> None:
    """扉ページの「窓」。押すと詳細ページへ移る。"""
    with st.container(key=f"window_{key}"):
        st.markdown(f'<div class="wt">{icon} {title}</div><div class="wq">{question}</div>'
                    f'<div class="wv">{teaser}</div>', unsafe_allow_html=True)
        st.page_link(page, label="詳しく見る →")


def setup(title: str, lead: str) -> None:
    _n["readout"] = 0
    st.markdown(CSS, unsafe_allow_html=True)
    st.title(title)
    st.caption(lead)


def insight(text: str, heading: str = "ここがポイント") -> None:
    st.markdown(f'<div class="insight"><h4>💡 {heading}</h4><p>{text}</p></div>', unsafe_allow_html=True)


def kpi(label: str, value: str | None, sub: str = "") -> None:
    v = value if value is not None else "—"
    s = sub if value is not None else "データ準備中"
    st.markdown(
        f'<div class="kpi"><div class="label">{label}</div><div class="value">{v}</div>'
        f'<div class="sub">{s}</div></div>',
        unsafe_allow_html=True,
    )


def pending(what: str, dataset_ids: list[str]) -> None:
    ds = data.datasets().set_index("id")
    names = "、".join(ds.loc[i, "name"] for i in dataset_ids if i in ds.index)
    st.markdown(
        f'<div class="pending">📦 <b>{what}</b><br><small>使うデータ: {names}（取得準備中）</small></div>',
        unsafe_allow_html=True,
    )


def sources(dataset_ids: list[str]) -> None:
    ds = data.datasets().set_index("id")
    with st.expander("このページのデータの出どころ"):
        for i in dataset_ids:
            r = ds.loc[i]
            st.markdown(f"- **{r['name']}**（{r['provider']}）… {r['status']}")

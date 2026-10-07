"""広域連携ページの共通部品（選んだ広域・自由に組んだ圏域の記憶）。

長野県の10広域（config/municipalities.csv の kouiki 列）から選ぶか、市町村をチェックして自由に圏域を組む。
"""
import pandas as pd
import streamlit as st

from . import muni

DEFAULT = "北アルプス"
CUSTOM = "自由に組む"
CUSTOM_DEFAULT = ["20212", "20485", "20486"]  # 大町市・白馬村・小谷村（例）


def names() -> list:
    return list(dict.fromkeys(muni.master().sort_index().kouiki))


def current() -> str:
    if "kouiki" not in st.session_state:
        q = st.query_params.get("k")
        st.session_state.kouiki = q if q in names() + [CUSTOM] else DEFAULT
    st.session_state.setdefault("kouiki_custom", CUSTOM_DEFAULT)
    return st.session_state.kouiki


def members(k: str | None = None) -> list:
    k = k or current()
    m = muni.master()
    if k == CUSTOM:
        return [c for c in st.session_state.get("kouiki_custom", CUSTOM_DEFAULT) if c in m.index]
    return list(m[m.kouiki == k].index)


def label(k: str | None = None) -> str:
    k = k or current()
    return "選んだ圏域" if k == CUSTOM else f"{k}広域"


def picker(page: str) -> tuple[str, list]:
    """広域を選ぶ欄。「自由に組む」を選ぶと、市町村のチェックボックスが出る。"""
    k = current()
    opts = names() + [CUSTOM]
    m = muni.master().sort_index()

    def _changed():
        st.session_state.kouiki = st.session_state[f"kouiki_pick_{page}"]

    def _toggle(c):
        cur = st.session_state.kouiki_custom
        st.session_state.kouiki_custom = [x for x in cur if x != c] if c in cur else cur + [c]

    with st.container(key="mpick"):
        c1, c2 = st.columns([1.2, 3], vertical_alignment="center")
        with c1:
            st.selectbox("広域を選ぶ", opts, index=opts.index(k), key=f"kouiki_pick_{page}", on_change=_changed,
                         format_func=lambda x: x if x == CUSTOM else f"{x}広域")
        mem = members(k)
        with c2:
            st.markdown(f'<div class="mmeta"><b>{label(k)}</b>　{len(mem)}市町村：'
                        + "・".join(m.loc[c, "name"] for c in mem) + "</div>", unsafe_allow_html=True)
        if k == CUSTOM:
            with st.expander("圏域に入れる市町村を選ぶ", expanded=len(mem) < 2):
                for kk, grp in m.groupby("kouiki", sort=False):
                    st.markdown(f'<div class="cmpk">{kk}</div>', unsafe_allow_html=True)
                    with st.container(horizontal=True, gap="small"):
                        for c, r in grp.iterrows():
                            st.checkbox(r["name"], value=c in mem, key=f"kc_{page}_{c}", on_change=_toggle, args=(c,))
    st.query_params["k"] = k
    return k, members(k)


def table() -> pd.DataFrame:
    """広域の一覧（index=広域名、name 列）。比べる欄で使う。"""
    ks = names()
    return pd.DataFrame({"name": [f"{k}広域" for k in ks], "kouiki": ["長野県の10広域"] * len(ks)}, index=ks)


SUM_NOTE = "広域の人数は市町村の観光来訪者数の合計（同じ日に2つの市町村を訪れた人は2人と数える）"


def monthly(codes: list) -> pd.Series:
    """圏域の月別観光来訪者数（市町村の合計）。"""
    v = muni.visitors()
    return v[[c for c in codes if c in v]].sum(axis=1)


@st.cache_data
def all_monthly() -> pd.DataFrame:
    """10広域の月別（列=広域名）。"""
    v = muni.visitors()
    m = muni.master()
    return v.T.groupby(m.kouiki.reindex(v.columns)).sum().T

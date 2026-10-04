"""市町村ページの共通部品（選んだ市町村の記憶・集計・県内での比較）。

元データは長野県「観光地利用者統計調査」の観光地ごとの明細（2011年〜）。市町村の数字は、
その市町村にある調査対象の観光地の合計（延べ人数）。人口は国勢調査（pipelines/population.py）。
"""
import pandas as pd
import streamlit as st

from . import charts, data

DEFAULT = "20201"  # 長野市
COLS = ["total", "kennai", "kengai", "higaeri", "shukuhaku", "spend"]


@st.cache_data
def master() -> pd.DataFrame:
    """市町村コード → 名前・広域・地域・宿泊統計の5エリア。"""
    m = pd.read_csv(data.CONFIG / "municipalities.csv", dtype={"code": str}).set_index("code")
    a = data.shukuhaku_area_map().set_index("municipality_code").area.str.replace("長野県", "")
    m["area5"] = a.reindex(m.index)
    return m


@st.cache_data
def annual() -> pd.DataFrame:
    """市町村×年の合計。月別は、月別の内訳がある観光地だけの合計（coverage はその割合）。"""
    sp = data.riyousha_spots()
    g = sp.groupby(["municipality_code", "year"])
    out = g[COLS].sum(min_count=1)
    out["spots"] = g.spot.nunique()
    has_m = sp[sp[charts.MONTHS].notna().all(axis=1)]
    mm = has_m.groupby(["municipality_code", "year"])[charts.MONTHS + ["total"]].sum()
    out = out.join(mm.drop(columns="total"))
    out["coverage"] = (mm.total / out.total).reindex(out.index)
    return out.reset_index()


@st.cache_data
def population() -> pd.Series:
    p = pd.read_parquet(data.PROCESSED / "population.parquet")
    return p[p.year == p.year.max()].set_index("municipality_code").population


@st.cache_data
def table(year: int) -> pd.DataFrame:
    """その年の、調査対象の観光地がある市町村の比較表（県内順位つき）。"""
    a = annual()
    cur = a[a.year == year].set_index("municipality_code")
    ly = a[a.year == year - 1].set_index("municipality_code")
    y19 = a[a.year == 2019].set_index("municipality_code")
    t = pd.DataFrame({
        "total": cur.total,
        "yoy": cur.total / ly.total.reindex(cur.index) - 1,
        "vs2019": cur.total / y19.total.reindex(cur.index) - 1,
        "kengai": cur.kengai / (cur.kennai + cur.kengai),
        "shuku": cur.shukuhaku / (cur.higaeri + cur.shukuhaku),
        "spend": cur.spend,
        "per_visit": cur.spend / cur.total,
        "per_resident": cur.total / population().reindex(cur.index),
        "spots": cur.spots,
    })
    t["name"] = master().name.reindex(t.index)
    t["kouiki"] = master().kouiki.reindex(t.index)
    return t


def rank(t: pd.DataFrame, col: str, code: str) -> str:
    r = t[col].rank(ascending=False)
    return f"{int(r[code])}位／{t[col].notna().sum()}" if code in r.index and pd.notna(r[code]) else "—"


def current() -> str:
    """いま選ばれている市町村（ページをまたいで覚える。URL の ?m= でも指定できる）。"""
    codes = master().index
    if "muni" not in st.session_state:
        q = st.query_params.get("m")
        st.session_state.muni = q if q in codes else DEFAULT
    return st.session_state.muni


def name(code: str) -> str:
    return master().name.get(code, code)


def picker(page: str) -> str:
    """市町村を選ぶ欄。変えると、すべての市町村タブがその市町村に切り替わる。"""
    m = master().sort_index()
    code = current()
    has = set(annual().municipality_code)

    def _changed():
        st.session_state.muni = st.session_state[f"muni_pick_{page}"]

    with st.container(key="mpick"):
        c1, c2 = st.columns([1.2, 3], vertical_alignment="center")
        with c1:
            st.selectbox("市町村を選ぶ", list(m.index), index=list(m.index).index(code), key=f"muni_pick_{page}",
                         format_func=lambda c: f"{m.loc[c, 'name']}（{m.loc[c, 'kouiki']}）", on_change=_changed)
        with c2:
            r = m.loc[code]
            note = "" if code in has else "　※ 県の観光地利用者統計調査に、この市町村の調査対象の観光地はありません"
            st.markdown(f'<div class="mmeta"><b>{r["name"]}</b>　{r.chiiki}地域・{r.kouiki}広域'
                        + (f'・宿泊統計の{r.area5}エリア' if isinstance(r.area5, str) else "") + f'{note}</div>',
                        unsafe_allow_html=True)
    st.query_params["m"] = code
    return code

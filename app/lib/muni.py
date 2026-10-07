"""市町村ページの共通部品（選んだ市町村の記憶・集計・県内での比較）。

市町村の人数は、日本観光振興協会「デジタル観光統計オープンデータ」の観光来訪者数（2021年〜、月別）。
同じ日に同じ市町村の観光地点を何か所回っても1人と数えるので、市町村の人数としてそのまま使える。

長野県「観光地利用者統計調査」は、県が選んだ観光地ごとの延べ人数なので、市町村の合計人数には使わない。
観光地ごとの順位・推移や、県内／県外・日帰り／宿泊の割合、1人あたり消費額（いずれも調査対象の観光地での値）に使う。
人口は国勢調査（pipelines/population.py）。
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


DIGITAL = data.PROCESSED / "digital_city.parquet"


def require_digital() -> None:
    """デジタル観光統計がまだ取り込まれていないときは、案内を出してページを止める。"""
    if not DIGITAL.exists() or not (data.PROCESSED / "digital_pref.parquet").exists():
        st.info("このページは、日本観光振興協会「デジタル観光統計オープンデータ」（市町村ごとの観光来訪者数）を使います。"
                "いまデータを取り込む準備をしているところです。取り込みが終わると表示されます。")
        st.page_link("views/9_data.py", label="使っている統計の一覧を見る →")
        st.stop()


@st.cache_data
def visitors() -> pd.DataFrame:
    """デジタル観光統計: 月×市町村の観光来訪者数（index=月初の日付、列=市町村コード）。"""
    d = pd.read_parquet(data.PROCESSED / "digital_city.parquet")
    return d.pivot_table(index="ym", columns="municipality_code", values="visitors", aggfunc="sum").sort_index()


@st.cache_data
def pref_visitors() -> pd.Series:
    """デジタル観光統計: 長野県（県単位で1日1人）の月別観光来訪者数。"""
    d = pd.read_parquet(data.PROCESSED / "digital_pref.parquet")
    return d[d.pref_code == 20].set_index("ym").visitors.sort_index()


def latest() -> tuple[int, int]:
    """いちばん新しい月の (年, 月)。"""
    v = visitors()
    return v.index.max().year, v.index.max().month


@st.cache_data
def yearly() -> pd.DataFrame:
    """12か月そろった年の、年×市町村の観光来訪者数。"""
    v = visitors()
    g = v.groupby(v.index.year)
    n = g.size()
    return g.sum()[n == 12]


@st.cache_data
def ytd(year: int, month: int) -> pd.Series:
    """その年の1〜month月の累計（市町村ごと）。"""
    v = visitors()
    return v[(v.index.year == year) & (v.index.month <= month)].sum()


@st.cache_data
def vtable() -> pd.DataFrame:
    """デジタル観光統計での比較表（index=市町村コード）。最新の年と、今年の1〜最新月。"""
    y = yearly()
    ly = int(y.index.max())
    Y, M = latest()
    pop = population()
    t = pd.DataFrame({
        "visitors": y.loc[ly],
        "yoy": y.loc[ly] / y.loc[ly - 1] - 1 if ly - 1 in y.index else float("nan"),
        "ytd": ytd(Y, M),
        "ytd_yoy": ytd(Y, M) / ytd(Y - 1, M) - 1,
        "per_resident": y.loc[ly] / pop.reindex(y.columns),
        "share": y.loc[ly] / y.loc[ly].sum(),
    })
    t["name"] = master().name.reindex(t.index)
    t["kouiki"] = master().kouiki.reindex(t.index)
    t.attrs.update(year=ly, Y=Y, M=M)
    return t


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

    def _changed():
        st.session_state.muni = st.session_state[f"muni_pick_{page}"]

    with st.container(key="mpick"):
        c1, c2 = st.columns([1.2, 3], vertical_alignment="center")
        with c1:
            st.selectbox("市町村を選ぶ", list(m.index), index=list(m.index).index(code), key=f"muni_pick_{page}",
                         format_func=lambda c: f"{m.loc[c, 'name']}（{m.loc[c, 'kouiki']}）", on_change=_changed)
        with c2:
            r = m.loc[code]
            st.markdown(f'<div class="mmeta"><b>{r["name"]}</b>　{r.chiiki}地域・{r.kouiki}広域'
                        + (f'・宿泊統計の{r.area5}エリア' if isinstance(r.area5, str) else "") + '</div>',
                        unsafe_allow_html=True)
    st.query_params["m"] = code
    return code


def compare_picker(code: str, page: str):
    """比べる市町村を選ぶ欄（lib.compare）。"""
    from . import compare
    return compare.picker(code, master().sort_index(), page)

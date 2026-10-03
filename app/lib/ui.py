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
</style>
"""


def setup(title: str, lead: str) -> None:
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

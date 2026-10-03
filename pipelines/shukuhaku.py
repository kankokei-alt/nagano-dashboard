"""観光庁「宿泊旅行統計調査」の都道府県別・月次の推移表を取り込む。

e-Stat の API には 2016年分の表しか登録されていない（2026年10月時点）ため、
観光庁のページで毎月更新される「推移表」(Excel) を直接読む。ファイルのURLは毎月変わるので、
ページから「推移表」のリンクを探して取得する。

使うシート（全施設ベース）:
  旧1-2 / 旧3-2 / 旧4-2 … 2011年1月〜2025年12月（確定値）
  1-1  / 3-1  / 4-1   … 2026年1月〜（第2次速報値）
  ※ 2026年1月分から層化基準が「従業者数」→「客室数」に変わった。前年比には見直しの影響が含まれうる。

出力: data/processed/shukuhaku_monthly.parquet（縦持ち）
  ym, pref_code, pref_name, metric, facility, value, status
  metric   … guests（延べ宿泊者数, 人泊）/ japanese / foreign / occupancy（客室稼働率, %）
  facility … 計 / 旅館 / リゾートホテル / … （occupancy のみ。ほかは「計」）
  status   … 確定 / 速報

使い方:
  python pipelines/shukuhaku.py              # 最新の推移表を取得して整形
  python pipelines/shukuhaku.py --file x.xlsx  # 手元のファイルを使う
"""
import argparse
import re
from pathlib import Path
from urllib.parse import urljoin

import openpyxl
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://www.mlit.go.jp/kankocho/tokei_hakusyo/shukuhakutokei.html"
RAW = ROOT / "data/raw/shukuhaku/suii.xlsx"
OUT = ROOT / "data/processed/shukuhaku_monthly.parquet"

SHEETS = {  # シート名: (metric, 確定/速報)
    "旧1-2": ("guests", "確定"), "旧2-2": ("japanese", "確定"),
    "旧3-2": ("foreign", "確定"), "旧4-2": ("occupancy", "確定"),
    "1-1": ("guests", "速報"), "2-1": ("japanese", "速報"),
    "3-1": ("foreign", "速報"), "4-1": ("occupancy", "速報"),
}
ERA = {"平成": 1988, "令和": 2018}


def download() -> Path:
    html = requests.get(PAGE, timeout=60).content.decode("utf-8")
    m = re.search(r'href="([^"]+\.xlsx)"[^>]*>(?:(?!</a>).)*?推移表', html, re.S)
    if not m:
        raise RuntimeError("観光庁のページに「推移表」のリンクが見つかりません。ページ構成が変わった可能性があります。")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(urljoin(PAGE, m.group(1)), timeout=180)
    r.raise_for_status()
    RAW.write_bytes(r.content)
    print(f"downloaded {urljoin(PAGE, m.group(1))}")
    return RAW


def _year(label) -> int | None:
    m = re.match(r"(平成|令和)(元|\d+)年", str(label or "").replace(" ", ""))
    if not m:
        return None
    return ERA[m.group(1)] + (1 if m.group(2) == "元" else int(m.group(2)))


def parse_sheet(ws, metric: str, status: str) -> pd.DataFrame:
    """3行目=年、4行目=月の見出し、5行目以降=都道府県（稼働率は2列目に施設タイプ）。"""
    rows = list(ws.iter_rows(values_only=True))
    first = 2 if metric == "occupancy" else 1  # 値が始まる列
    years, months, y = rows[2], rows[3], None
    cols = {}
    for j in range(first, len(months)):
        y = _year(years[j]) or y
        m = re.match(r"(\d+)月", str(months[j] or ""))
        if y and m:
            cols[j] = pd.Timestamp(y, int(m.group(1)), 1)

    recs, pref = [], None
    for r in rows[4:]:
        if isinstance(r[0], str) and r[0].startswith("※"):
            break
        if r[0]:
            pref = str(r[0]).replace("　", "")
        if pref is None:
            continue
        facility = re.sub(r"\s", "", str(r[1])) if metric == "occupancy" else "計"
        for j, ym in cols.items():
            v = r[j] if j < len(r) else None
            if isinstance(v, (int, float)):
                recs.append((ym, pref, facility, float(v)))
    df = pd.DataFrame(recs, columns=["ym", "pref", "facility", "value"])
    code = df.pref.str.extract(r"^(\d{2})")[0]
    df["pref_code"] = code.fillna("00")
    df["pref_name"] = df.pref.str.replace(r"^\d{2}", "", regex=True)
    df["metric"], df["status"] = metric, status
    return df.drop(columns="pref")


def build(path: Path) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True)
    parts = [parse_sheet(wb[s], *meta) for s, meta in SHEETS.items() if s in wb.sheetnames]
    df = pd.concat(parts, ignore_index=True)
    # 速報と確定が重なる月があれば確定を優先
    df = (df.sort_values("status")  # 「確定」<「速報」
            .drop_duplicates(["ym", "pref_code", "metric", "facility"])
            .sort_values(["metric", "pref_code", "facility", "ym"])
            .reset_index(drop=True))
    return df[["ym", "pref_code", "pref_name", "metric", "facility", "value", "status"]]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, help="取得済みの推移表 Excel")
    a = p.parse_args()
    df = build(a.file or download())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    nagano = df[(df.pref_code == "20") & (df.metric == "guests")]
    print(f"wrote {OUT} ({len(df):,} rows) / 長野県 延べ宿泊者数 {nagano.ym.min():%Y-%m}〜{nagano.ym.max():%Y-%m}")


if __name__ == "__main__":
    main()

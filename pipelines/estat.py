"""e-Stat API (v3.0) の最小クライアント。

アプリケーションIDは環境変数 ESTAT_APP_ID で渡す（リポジトリには書かない）。
  発行: e-Stat にログイン → マイページ → API機能(アプリケーションID発行)

使い方:
  # 統計表を探す（例: 宿泊旅行統計調査）
  python pipelines/estat.py search 宿泊旅行統計調査 --limit 30
  # 統計表を取得して CSV に保存
  python pipelines/estat.py get <statsDataId> --where cdArea=20000
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.e-stat.go.jp/rest/3.0/app/json"
ROOT = Path(__file__).resolve().parents[1]


def _app_id() -> str:
    app_id = os.environ.get("ESTAT_APP_ID")
    if not app_id:
        sys.exit("ESTAT_APP_ID が未設定です。e-Stat のアプリケーションIDを環境変数に設定してください。")
    return app_id


def search(keyword: str, limit: int = 50) -> pd.DataFrame:
    r = requests.get(
        f"{BASE}/getStatsList",
        params={"appId": _app_id(), "searchWord": keyword, "limit": limit},
        timeout=60,
    )
    r.raise_for_status()
    tables = r.json()["GET_STATS_LIST"]["DATALIST_INF"].get("TABLE_INF", [])
    if isinstance(tables, dict):
        tables = [tables]
    return pd.DataFrame(
        {
            "id": t["@id"],
            "stat": t["STAT_NAME"]["$"],
            "title": t["TITLE"]["$"] if isinstance(t["TITLE"], dict) else t["TITLE"],
            "survey_date": t.get("SURVEY_DATE"),
            "updated": t.get("UPDATED_DATE"),
        }
        for t in tables
    )


def get_data(stats_data_id: str, **filters: str) -> pd.DataFrame:
    """統計表の値をコード名つきの縦持ち DataFrame で返す（ページングに対応）。"""
    params = {"appId": _app_id(), "statsDataId": stats_data_id, "metaGetFlg": "Y", **filters}
    rows, labels = [], {}
    while True:
        r = requests.get(f"{BASE}/getStatsData", params=params, timeout=120)
        r.raise_for_status()
        sd = r.json()["GET_STATS_DATA"]["STATISTICAL_DATA"]
        if not labels:
            for obj in sd["CLASS_INF"]["CLASS_OBJ"]:
                cls = obj["CLASS"] if isinstance(obj["CLASS"], list) else [obj["CLASS"]]
                labels[obj["@id"]] = {c["@code"]: c["@name"] for c in cls}
        values = sd["DATA_INF"]["VALUE"]
        rows.extend(values if isinstance(values, list) else [values])
        nxt = sd["RESULT_INF"].get("NEXT_KEY")
        if not nxt:
            break
        params["startPosition"] = nxt

    df = pd.DataFrame(rows).rename(columns={"$": "value"})
    df.columns = [c.lstrip("@") for c in df.columns]
    for key, mapping in labels.items():
        if key in df.columns:
            df[f"{key}_name"] = df[key].map(mapping)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("keyword")
    s.add_argument("--limit", type=int, default=50)
    g = sub.add_parser("get")
    g.add_argument("stats_data_id")
    g.add_argument("--where", action="append", default=[], help="例: cdArea=20000")
    a = p.parse_args()

    if a.cmd == "search":
        print(search(a.keyword, a.limit).to_string(index=False))
    else:
        filters = dict(w.split("=", 1) for w in a.where)
        df = get_data(a.stats_data_id, **filters)
        out = ROOT / f"data/raw/estat/{a.stats_data_id}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()

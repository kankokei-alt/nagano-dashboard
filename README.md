# 長野県 観光分析ダッシュボード

長野県観光機構・地域DMO・観光協会の方が、公的統計から長野県観光の「いま」と「これから」をつかむためのダッシュボードです。

- **データに詳しくない人が、迷わず読める**ことを最優先にしています。各ページの最初にある「ここがポイント」に要点を書き、数字やグラフは絞っています。
- 目的ごとにページ（タブ）を分けています。
- 地図は国土数値情報の正確な行政区域ポリゴンで描きます。外部の地図タイルを使わないので、庁内ネットワークでも表示できます。

## ページ構成

| ページ | 見る人の問い | 主なデータ |
|---|---|---|
| 🗾 長野県を俯瞰する | 県全体でいま何が起きている？ | 宿泊旅行統計、観光入込客統計、JNTO |
| 🔍 市町村を深掘りする | うちのまちのどのエリアが伸びている？（例: 長野市の中心市街地・松代・戸隠） | 観光地利用者統計、デジタル観光統計、国勢調査の小地域境界 |
| 🤝 広域で連携する | 圏域の中で集中している所・周遊の余地がある所は？ | 観光地利用者統計、デジタル観光統計 |
| 📈 稼働率予測（ベータ版） | この先の客室稼働率は上がる？下がる？ | 宿泊旅行統計、気象、祝日・連休、イベント |
| 📚 データについて | このデータはどこから来ている？ | ― |

## 動かし方

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# データの準備（取得済みのものは data/processed/ に入っています）
python pipelines/fetch_boundaries.py   # 行政区域ポリゴン（国土数値情報 N03）
python pipelines/build_calendar.py     # 祝日・連休カレンダー

streamlit run app/main.py
```

e-Stat API を使う取得には、アプリケーションIDを環境変数で渡します（**リポジトリには書かない**）。

```bash
export ESTAT_APP_ID=xxxxxxxx
python pipelines/estat.py search 宿泊旅行統計調査
```

## フォルダ

```
config/      市町村マスタ（10広域・4地域）、市町村内エリアの定義、イベント、データ一覧
pipelines/   取得・整形スクリプト
data/raw/        取得したままのデータ（git 管理外）
data/processed/  ダッシュボードが読む整形済みデータ
app/         Streamlit アプリ（main.py と views/ に各ページ）
models/      稼働率予測モデル（これから）
```

## データの取り込み状況

一覧は `config/datasets.csv`（アプリの「データについて」ページにも表示）を参照してください。

開発用のクラウド環境は、ネットワーク制限で官公庁サイトに接続できません。取り込みを進めるには、環境のネットワーク設定で次のドメインを許可してください。

```
api.e-stat.go.jp, www.e-stat.go.jp, www.mlit.go.jp, nlftp.mlit.go.jp,
www.pref.nagano.lg.jp, www.jnto.go.jp, statistics.jnto.go.jp,
www.data.jma.go.jp, www8.cao.go.jp, www.nihon-kankou.or.jp
```

## 出典

- 行政区域: 国土数値情報（行政区域データ N03, 2020年1月1日時点）国土交通省 … [niiyz/JapanCityGeoJson](https://github.com/niiyz/JapanCityGeoJson) が GeoJSON に変換したものを取得して加工
- 祝日: 内閣府「国民の祝日」（`jpholiday` パッケージ経由）

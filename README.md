# Graphiti Simple Chat Bot

> [!NOTE]
> 千手観音PJ: uniQornチームの1技術、Graphitiを使ったシンプルなチャットボットです
> 
> uniQornは、[千手観音プロジェクト～ASI時代を切り拓く新プロジェクト始動～](https://wiki.workers-hub.com/pages/viewpage.action?pageId=2691270575)で上位20チームに残った24卒同期で業務効率化AIを開発しているチームです。
> 
> 24卒同期の11名で構成されていますが、このGraphitiをよく触っている開発者は、ytonoyam, saoku, stakakurです。:BIG KANSYA:

> [!NOTE]
> もし動かなかった場合は、PRか ytonoyam までDMをお願いしますmm
>  
> PRが飛んできたら泣いて喜びます🙏

**「現在、チームにはどのような問題が存在するのか？」**

一見、簡単そうな質問に見えますが、ベクトル検索では、

- タスクの依存関係の把握
- 時系列の把握

は構造上把握は難しいという特徴があります。

**ナレッジグラフを使うアプリだからこその出力を得られている**という図です(感動の涙)

<img width="1375" alt="image" src="https://ghe.corp.yahoo.co.jp/ytonoyam/graphiti-simple-chat/assets/13362/09596c44-3ce8-42f6-8726-1ffa51e88a2a">


<img width="811" alt="スクリーンショット 2025-11-26 6 18 26" src="https://ghe.corp.yahoo.co.jp/ytonoyam/graphiti-simple-chat/assets/13362/05c79cf2-8d62-4924-a7d2-6a5df5c3c66c">

[Graphiti](https://github.com/getzep/graphiti)は、時間情報付きナレッジグラフの自動構築・更新システムです。
ベクトルDBであるNeo4jとOpenAI APIを組み合わせ、動的に変化するデータからリアルタイムに知識グラフを生成し、ハイブリッド検索（埋め込み + BM25 + グラフ探索）で情報を取得できます。Neo4jは公式のDocker Image(Apache 2.0)を使っています。

**graphiti-core(Apache 2.0)がライブラリとして存在しており、そのライブラリをGraphiti MCP(uniQornの自作)で作成しています。**
**そのため、社内でも本ライブラリおよびMCPは利用可能です。[MCPに関する確認・問い合わせフロー / MCP Confirmation and Inquiry Flow](https://wiki.workers-hub.com/pages/viewpage.action?pageId=2592343328)のケースBに該当します。**

## 必要な環境

- Docker 20.10以降
- Docker Compose v2.0以降
- OpenAI API Key
- make

## クイックスタート

### セットアップと起動

```bash
# 1. Graphitiリポジトリのクローン
git clone git@ghe.corp.yahoo.co.jp:ytonoyam/graphiti-simple-chat.git
cd graphiti

# 2. .envファイルを編集してAPIキーを設定
cp .env.example .env
nano .env  # または vim .env、code .env など
# 必須項目:
#   - LLM__PROVIDERS__OPENAI__API_KEY（PAT）
#   - OPENAI_API_KEY（バックエンド用、同じキー）
#   - GITHUB_TOKEN（GitHub連携する場合）

# 3. ワンコマンドでセットアップと起動
make quick-start

# 4. デモデータをLLMでナレッジグラフに変換
make demo
```

### 推奨LLMモデル

gpt-4o-mini以上あれば十分です。gpt-5は時間がかなりかかるのでタイパよくありません。

### アクセスURL

起動完了後、以下のURLでアクセスできます：

| サービス | URL | 認証情報 |
|---------|-----|---------|
| フロントエンドUI | http://localhost:20002 | なし |
| Neo4j Browser | http://localhost:20474 | user: `neo4j`, pass: `password123` |
| バックエンドAPI | http://localhost:20001/docs | なし |
| Graphiti MCP | http://localhost:30547 | なし |
| MinIO Console | http://localhost:20735 | user: `minio`, pass: `miniosecret` |

### 動作確認

```bash
# Makefileを使用する場合
make health

# 手動で確認する場合
curl http://localhost:30547/health
curl http://localhost:20001/health
```

## Makefileコマンド一覧

超便利なMakefileコマンドを用意しています。詳細は `make help` で確認できます。

### 基本操作

```bash
make help          # ヘルプを表示
make setup         # 初期セットアップ
make start         # サービス起動
make stop          # サービス停止
make restart       # サービス再起動
make ps            # サービス状態確認
make health        # ヘルスチェック
```

### ログ確認

```bash
make logs          # 全サービスのログ
make logs-mcp      # Graphiti MCPのログ
make logs-neo4j    # Neo4jのログ
make logs-backend  # バックエンドのログ
make logs-frontend # フロントエンドのログ
```

### データ取り込み

```bash
# GitHub Issues
make ingest-github \
  GITHUB_TOKEN=ghp_xxx \
  GITHUB_OWNER=owner \
  GITHUB_REPO=repo

# Slack Messages
make ingest-slack \
  SLACK_TOKEN=xoxc-xxx \
  SLACK_COOKIE= \
  CHANNEL_ID=C... \
  DAYS=7

# Zoom Transcripts (data/zoom/にVTTファイルを配置後)
# デモデータは既に配置してあります
make ingest-zoom
```

### データベース操作

```bash
make shell-neo4j      # Neo4j Cypherシェル
make shell-mcp        # MCPコンテナのシェル
make query-episodes   # エピソード一覧
make query-entities   # エンティティ一覧
make query-facts      # Facts一覧
```

### 検索

```bash
make search QUERY="your search query"
```

### クリーンアップ

```bash
make clean         # コンテナを停止・削除
make clean-data    # すべてのデータを削除（警告: データが失われます）
make clean-cache   # Pythonキャッシュをクリア
```

## 📚 詳細なドキュメント

### アーキテクチャとデータモデル

- **[METADATA_SPECIFICATION.md](docs/METADATA_SPECIFICATION.md)** - メタデータ仕様の完全ガイド（Episode/Node/Edge/Citation）
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - システムアーキテクチャの詳細（3層分離構造、通信フロー）
- **[DATA_INGESTION.md](docs/DATA_INGESTION.md)** - データ取り込みガイド（GitHub/Slack/Zoom、カスタムデータソース）

### セットアップとトラブルシューティング

- **[SETUP.md](SETUP.md)** - 詳細なセットアップガイド、トラブルシューティング

### API仕様とGraphiti公式リソース

- **[REST API仕様](docs/REST_API.md)** - 自作Graphiti MCPのAPI仕様とエンドポイント

#### Graphiti公式リソース
- **[Graphiti公式ドキュメント](https://help.getzep.com/graphiti/)** - Graphitiの公式ドキュメント
- **[GitHub Repository](https://github.com/getzep/graphiti)** - Graphiti Coreのソースコード（Apache 2.0）
- **[Quick Start Guide](https://help.getzep.com/graphiti/getting-started/quick-start)** - 公式クイックスタート
- **[Custom Entity Types](https://help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types)** - カスタムエンティティタイプの作成方法
- **[Searching the Graph](https://help.getzep.com/graphiti/working-with-data/searching)** - グラフ検索のガイド

## 使用方法

### 1. MCPサーバーとして使用 (Claude Desktop/Cursor)

Claude DesktopやCursorの設定ファイルに以下を追加:

```json
{
  "mcpServers": {
    "graphiti": {
      "url": "http://localhost:30547/mcp/",
      "timeout": 30000
    }
  }
}
```

利用可能なMCPツール:
- `add_memory`: エピソードを知識グラフに追加
- `search_facts`: ナレッジグラフを検索
- `get_entity`: エンティティの詳細を取得

### 2. REST API経由で使用

```bash
# 検索
curl -X POST http://localhost:30547/graph/search \
  -H "Content-Type: application/json" \
  -d '{"query": "会議の議題", "limit": 10}'

# エピソード追加
curl -X POST http://localhost:30547/graph/episodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "meeting_001",
    "content": "プロジェクトキックオフミーティング",
    "source": "manual",
    "source_description": "手動入力"
  }'
```

詳細は[REST API仕様](server/docs/REST_API.md)を参照してください。

## プロジェクト構造

```
graphiti/
├── Makefile              # 便利なコマンド集
├── docker-compose.yml    # Docker Compose設定
├── Dockerfile            # MCPサーバーのDockerfile
├── .env.example          # 環境変数テンプレート
├── SETUP.md              # 詳細セットアップガイド
├── README.md             # このファイル
├── server/               # MCPサーバー
│   ├── src/             # サーバーソースコード
│   │   ├── ingestion/           # データ取り込みモジュール
│   │   │   ├── base.py         # 基底クラス
│   │   │   ├── github.py       # GitHub取り込み
│   │   │   ├── slack.py        # Slack取り込み
│   │   │   └── zoom.py         # Zoom取り込み
│   │   ├── scripts/            # CLIスクリプト
│   │   │   ├── ingest_github.py
│   │   │   ├── ingest_slack.py
│   │   │   └── ingest_zoom.py
│   │   ├── translator.py       # 翻訳ユーティリティ
│   │   ├── config/             # 設定
│   │   ├── models/             # データモデル
│   │   ├── routers/            # APIルーター
│   │   └── services/           # サービス層
│   └── docs/            # サーバーのドキュメント
├── backend/              # 検索Bot API
├── frontend/             # 検索Bot UI
├── data/                 # データ保存ディレクトリ
│   ├── github/          # GitHub Issues
│   ├── slack/           # Slackメッセージ
│   └── zoom/            # Zoom文字起こし
├── docs/                 # プロジェクトドキュメント
└── tests/                # テスト
```

## データ取り込み

### 概要

Graphiti MCPは、複数のデータソースからデータを取り込み、ソースへのURLを自動的に保存します。すべてのデータは英語に自動翻訳されてインデックス化されます。

### 対応データソース

1. Slack - メッセージとスレッド（自動英語翻訳）
2. GitHub - Issues（コメント含む、自動英語翻訳）
3. Zoom - 文字起こしVTTファイル（MinIOに保存、自動英語翻訳）

### GitHub Issuesの取り込み

```bash
# Makefileを使用（推奨）
make ingest-github \
  GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  GITHUB_OWNER=hoge-org \
  GITHUB_REPO=hoge-zoom

# 手動で実行
docker compose exec -e GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  -e GITHUB_OWNER=hoge-org \
  -e GITHUB_REPO=hoge-zoom \
  graphiti-mcp python src/scripts/ingest_github.py
```

Issue URLは `https://github.com/{owner}/{repo}/issues/{number}` 形式で保存されます。

### Slackメッセージの取り込み

```bash
# Makefileを使用（推奨）
make ingest-slack \
  SLACK_TOKEN=xoxc-xxxxxxxxxxxx \
  WORKSPACE_ID=T09HNJQG1JA \
  CHANNEL_ID=C09JQQMUHCZ \
  DAYS=7

# 手動で実行
docker compose exec -e SLACK_TOKEN=xoxc-xxxxxxxxxxxx \
  graphiti-mcp python src/scripts/ingest_slack.py \
  --token xoxc-xxxxxxxxxxxx \
  --workspace-id T09HNJQG1JA \
  --channel-id C09JQQMUHCZ \
  --days 7
```

メッセージURLは `https://app.slack.com/client/{workspace}/{channel}/p{timestamp}` 形式で保存されます。

### Zoom文字起こしの取り込み

```bash
# 1. VTTファイルをdata/zoom/に配置
cp /path/to/meeting_transcript.vtt data/zoom/

# 2. 取り込み実行（Makefile推奨）
make ingest-zoom

# 手動で実行
docker compose exec graphiti-mcp python src/scripts/ingest_zoom.py --data-dir data/zoom
```

文字起こしファイルはMinIOにアップロードされ、URLは `http://localhost:20734/zoom-transcripts/{uuid}_transcript.vtt` 形式になります。

### 英語翻訳の無効化

翻訳を無効化するには `--no-translate` フラグを使用します：

```bash
docker compose exec graphiti-mcp python src/scripts/ingest_github.py --no-translate
docker compose exec graphiti-mcp python src/scripts/ingest_slack.py --no-translate --token xxx ...
docker compose exec graphiti-mcp python src/scripts/ingest_zoom.py --no-translate --data-dir data/zoom
```

### ソースURLの確認方法

取り込んだデータのソースURLは、検索結果に含まれます：

```bash
# REST API経由で検索
curl -X POST http://localhost:30547/graph/search \
  -H "Content-Type: application/json" \
  -d '{"query": "会議の議題", "limit": 10}' | python3 -m json.tool

# 結果にcitationsが含まれる
# {
#   "fact": "...",
#   "citations": [
#     {
#       "source_url": "https://github.com/owner/repo/issues/123",
#       "episode_name": "github:issue:owner/repo#123"
#     }
#   ]
# }
```

## 開発

### ローカル開発環境のセットアップ

```bash
# Python仮想環境を作成
python3.12 -m venv .venv
source .venv/bin/activate

# 依存関係のインストール
pip install -e ".[dev]"
```

### テストの実行

```bash
# Neo4jとGraphiti MCPが起動していることを確認
make start

# テスト実行
python tests/test_graphiti.py
```

### ログの確認

```bash
# Makefileを使用
make logs           # 全サービス
make logs-mcp       # Graphiti MCPのみ
make logs-neo4j     # Neo4jのみ

# Docker Composeを直接使用
docker compose logs -f
docker compose logs -f graphiti-mcp
docker compose logs -f neo4j
```

## コード品質

このプロジェクトは包括的なリファクタリング（Phase 1-12）を経て、高品質なコードベースを維持しています：

- ✅ **可読性**: 日本語コメント→英語、ネスト深度削減（6レベル→2レベル）
- ✅ **保守性**: 長いメソッド分割（274行→70行）、モジュール化
- ✅ **型安全性**: Pydanticデータクラス、パラメータ削減（9個→1個）
- ✅ **テスト済み**: Docker環境で全機能動作確認済み

詳細は[docs/](docs/)ディレクトリの技術ドキュメントを参照してください。

## コントリビューション

PRを投げて頂けるとytonoyamとuniQornの同期たちが泣いて喜びます

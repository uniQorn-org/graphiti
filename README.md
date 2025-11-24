# Graphiti MCP - Real-Time Knowledge Graph Server

Graphiti MCPは、[Graphiti](https://github.com/getzep/graphiti)を使用した時間情報付きナレッジグラフの自動構築・更新システムです。Neo4jとOpenAI APIを組み合わせ、動的に変化するデータからリアルタイムに知識グラフを生成し、ハイブリッド検索（埋め込み + BM25 + グラフ探索）で素早く情報を取得できます。

## 特徴

- **リアルタイム増分更新**: 新規データ（エピソード）を即座に反映
- **二重時間モデル**: 出来事の発生時刻と取り込み時刻を別トラックで管理
- **ハイブリッド検索**: 埋め込み・BM25・グラフトラバーサルを組み合わせた高度な検索
- **柔軟なオントロジー**: Pydanticで独自のエンティティ/エッジ型を定義可能
- **MCPサーバー**: Model Context Protocol対応で、Claude DesktopやCursorから利用可能
- **REST API**: FastAPIベースのHTTP APIでプログラマティックにアクセス可能
- **自動英語翻訳**: 日本語データを自動的に英語に翻訳してインデックス化
- **ソース追跡**: すべてのFactにソースURL（Slack、GitHub、Zoom）を自動保存

## 必要な環境

- **Docker** 20.10以降
- **Docker Compose** v2.0以降
- **OpenAI API Key**
- **make** (オプション、推奨)

## クイックスタート

### 🚀 Makefileを使用する方法（推奨）

最も簡単な方法です：

```bash
# 1. リポジトリのクローン
git clone https://github.com/uniQorn-org/graphiti.git
cd graphiti

# 2. ワンコマンドでセットアップと起動
make quick-start
```

初回実行時は、OpenAI APIキーの設定を求められます。`.env`ファイルを編集して設定してください：

```bash
# .envファイルを編集
nano .env  # または vim .env、code .env など
# OPENAI_API_KEY=your_openai_api_key_here を設定

# 再度起動
make start
```

### 📦 Docker Composeを直接使用する方法

Makefileを使用しない場合：

```bash
# 1. リポジトリのクローン
git clone https://github.com/uniQorn-org/graphiti.git
cd graphiti

# 2. 環境変数の設定
cp .env.example .env
nano .env  # OPENAI_API_KEYを設定

# 3. データディレクトリの作成
mkdir -p data/github data/slack data/zoom

# 4. サービスの起動
docker compose up -d

# 5. 健全性確認
docker compose ps
```

### アクセスURL

起動完了後、以下のURLでアクセスできます：

| サービス | URL | 認証情報 |
|---------|-----|---------|
| **フロントエンドUI** | http://localhost:20002 | なし |
| **Neo4j Browser** | http://localhost:7474 | user: `neo4j`, pass: `password123` |
| **バックエンドAPI** | http://localhost:20001/docs | なし |
| **Graphiti MCP** | http://localhost:30547 | なし |
| **MinIO Console** | http://localhost:20735 | user: `minio`, pass: `miniosecret` |

### 動作確認

```bash
# Makefileを使用する場合
make health

# 手動で確認する場合
curl http://localhost:30547/health
curl http://localhost:20001/health
```

## Makefileコマンド一覧

便利なMakefileコマンドを用意しています。詳細は `make help` で確認できます。

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
  WORKSPACE_ID=T... \
  CHANNEL_ID=C... \
  DAYS=7

# Zoom Transcripts (data/zoom/にVTTファイルを配置後)
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

- **[SETUP.md](SETUP.md)** - 詳細なセットアップガイド、トラブルシューティング
- **[Graphiti解説 (日本語)](docs/graphiti.md)** - Graphitiの仕組みと使い方
- **[REST API仕様](server/docs/REST_API.md)** - API仕様とエンドポイント
- **[Graphiti公式ドキュメント](https://help.getzep.com/graphiti/)** - Graphiti本体のドキュメント

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

### 2. Pythonクライアントとして使用

```python
import asyncio
from client.graphiti_client import GraphitiClient

async def main():
    # クライアント作成
    client = GraphitiClient(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password123"
    )

    # インデックス/制約の構築（初回のみ）
    await client.ensure_ready()

    # エピソード追加
    await client.add_episode(
        name="meeting_2024_01_15",
        episode_body="2024年1月15日の会議で、新機能の実装計画を議論しました。",
        source="user_input",
        source_description="定例会議の議事録"
    )

    # 検索
    results = await client.search("新機能の実装計画")
    print(results)

    # クライアントを閉じる
    await client.close()

asyncio.run(main())
```

### 3. REST API経由で使用

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
├── client/               # Pythonクライアント
├── server/               # MCPサーバー
│   ├── src/             # サーバーソースコード
│   │   ├── ingest_github.py     # GitHub取り込みスクリプト
│   │   ├── ingest_slack.py      # Slack取り込みスクリプト
│   │   ├── ingest_zoom.py       # Zoom取り込みスクリプト
│   │   └── translator.py        # 翻訳ユーティリティ
│   ├── scripts/         # 補助スクリプト
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

1. **Slack** - メッセージとスレッド（自動英語翻訳）
2. **GitHub** - Issues（コメント含む、自動英語翻訳）
3. **Zoom** - 文字起こしVTTファイル（MinIOに保存、自動英語翻訳）

### GitHub Issuesの取り込み

```bash
# Makefileを使用（推奨）
make ingest-github \
  GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  GITHUB_OWNER=uniQorn-org \
  GITHUB_REPO=uniqorn-zoom

# 手動で実行
docker compose exec -e GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  -e GITHUB_OWNER=uniQorn-org \
  -e GITHUB_REPO=uniqorn-zoom \
  graphiti-mcp python src/ingest_github.py
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
  graphiti-mcp python src/ingest_slack.py \
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
docker compose exec graphiti-mcp python src/ingest_zoom.py --zoom-dir data/zoom
```

文字起こしファイルはMinIOにアップロードされ、URLは `http://localhost:20734/zoom-transcripts/{uuid}_transcript.vtt` 形式になります。

### 英語翻訳の無効化

翻訳を無効化するには `--no-translate` フラグを使用します：

```bash
docker compose exec graphiti-mcp python src/ingest_github.py --no-translate
docker compose exec graphiti-mcp python src/ingest_slack.py --no-translate --token xxx ...
docker compose exec graphiti-mcp python src/ingest_zoom.py --no-translate --zoom-dir data/zoom
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

## トラブルシューティング

よくある問題と解決方法は[SETUP.md](SETUP.md#トラブルシューティング)に記載しています。

### Neo4jが起動しない

`.env`ファイルでメモリ設定を調整:

```env
NEO4J_HEAP_INITIAL_SIZE=256M
NEO4J_HEAP_MAX_SIZE=512M
NEO4J_PAGECACHE_SIZE=256M
```

### OpenAI APIのレート制限エラー (429)

`.env`ファイルで並列度を調整:

```env
SEMAPHORE_LIMIT=5  # Tierに応じて 1-50
```

- Tier 1 (無料): 1-2
- Tier 2: 5-8
- Tier 3: 10-15
- Tier 4: 20-50

### コンテナの完全リセット

```bash
# Makefileを使用
make clean-data
make start

# Docker Composeを直接使用
docker compose down -v
docker compose up -d
```

詳細は[SETUP.md](SETUP.md)を参照してください。

## 社内検索Bot

### 概要

LangChain + Graphitiを使った対話型社内検索システムです。

### 主な機能

1. **AIチャット** - 自然言語で質問すると、ナレッジグラフを検索して回答
2. **手動検索** - キーワードでナレッジグラフを直接検索
3. **Fact編集** - 検索結果から間違った情報を修正可能

### 使い方

```bash
# 起動
make start

# アクセス
# フロントエンド: http://localhost:20002
# バックエンドAPI: http://localhost:20001/docs
```

詳細は以下を参照：
- [バックエンド README](backend/README.md)
- [フロントエンド README](frontend/README.md)

## ライセンス

Apache-2.0

## コントリビューション

Issue・Pull Requestを歓迎します！

## サポート

- **ドキュメント**: [SETUP.md](SETUP.md)、[docs/](docs/)
- **Issue**: https://github.com/uniQorn-org/graphiti/issues
- **Graphiti公式**: https://help.getzep.com/graphiti/

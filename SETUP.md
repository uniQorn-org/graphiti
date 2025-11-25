# Graphiti MCP - セットアップガイド

このドキュメントでは、Graphiti MCPの環境構築手順を詳しく説明します。

## 目次

- [前提条件](#前提条件)
- [クイックスタート](#クイックスタート)
- [詳細なセットアップ手順](#詳細なセットアップ手順)
- [環境変数の設定](#環境変数の設定)
- [データ取り込み](#データ取り込み)
- [トラブルシューティング](#トラブルシューティング)

## 前提条件

以下のソフトウェアがインストールされている必要があります：

### 必須

- **Docker** (20.10以降)
- **Docker Compose** (v2.0以降)
- **OpenAI API Key**

### オプション（開発時）

- **Python 3.12+**
- **make**（Makefileを使用する場合）
- **curl**（APIテスト用）

### インストール確認

```bash
# Dockerのバージョン確認
docker --version
# 例: Docker version 24.0.0

# Docker Composeのバージョン確認
docker compose version
# 例: Docker Compose version v2.20.0

# makeのインストール確認（オプション）
make --version
```

## クイックスタート

最も簡単な方法でGraphiti MCPを起動します。

### 1. リポジトリのクローン

```bash
git clone https://github.com/uniQorn-org/graphiti.git
cd graphiti
```

### 2. Makefileを使用したセットアップ（推奨）

```bash
# 初期セットアップ（.envファイルの作成とディレクトリの準備）
make setup

# .envファイルを編集してOpenAI APIキーを設定
# エディタで .env を開いて OPENAI_API_KEY を設定してください
nano .env  # または vim .env、code .env など

# すべてのサービスを起動
make start
```

起動が完了すると、以下のURLでアクセスできます：

- **フロントエンドUI**: http://localhost:20002
- **Neo4j Browser**: http://localhost:20474 (user: `neo4j`, password: `password123`)
- **バックエンドAPI**: http://localhost:20001/docs
- **Graphiti MCP**: http://localhost:30547
- **MinIO Console**: http://localhost:20735 (user: `minio`, password: `miniosecret`)

### 3. Makefileを使用しない場合

```bash
# .envファイルを作成
cp .env.example .env

# .envファイルを編集してOPENAI_API_KEYを設定
nano .env

# データディレクトリを作成
mkdir -p data/github data/slack data/zoom

# サービスを起動
docker compose up -d

# 起動確認
docker compose ps
```

## 詳細なセットアップ手順

### ステップ1: 環境変数ファイルの作成

`.env.example`をコピーして`.env`ファイルを作成します：

```bash
cp .env.example .env
```

### ステップ2: 環境変数の設定

`.env`ファイルを編集して、必須の設定を行います：

```bash
# エディタで開く（お好みのエディタを使用）
nano .env
# または
vim .env
# または
code .env
```

**最小限の設定例**:

```env
# 必須: OpenAI API Key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx

# オプション: デフォルト値が設定されています
OPENAI_MODEL=gpt-4o-mini
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
```

詳細な環境変数については、[環境変数の設定](#環境変数の設定)セクションを参照してください。

### ステップ3: データディレクトリの作成

データ取り込み用のディレクトリを作成します：

```bash
mkdir -p data/github data/slack data/zoom
```

これらのディレクトリは以下の用途で使用されます：
- `data/github/`: GitHub Issuesの保存先
- `data/slack/`: Slackメッセージの保存先
- `data/zoom/`: Zoom VTTトランスクリプトの保存先

### ステップ4: Dockerイメージのビルド

初回起動時は、Dockerイメージをビルドします：

```bash
# Makefileを使用する場合
make build

# Docker Composeを直接使用する場合
docker compose build
```

### ステップ5: サービスの起動

すべてのサービスを起動します：

```bash
# Makefileを使用する場合
make start

# Docker Composeを直接使用する場合
docker compose up -d
```

起動するサービス：
- **neo4j**: Neo4jグラフデータベース
- **graphiti-mcp**: Graphiti MCPサーバー
- **search-bot-backend**: FastAPIバックエンド
- **search-bot-frontend**: Reactフロントエンド
- **minio**: MinIOオブジェクトストレージ
- **minio-init**: MinIOの初期化コンテナ

### ステップ6: サービスの健全性確認

サービスが正常に起動したか確認します：

```bash
# Makefileを使用する場合
make health

# 手動で確認する場合
docker compose ps
```

すべてのサービスが`healthy`または`running`状態になっていることを確認してください。

### ステップ7: 動作確認

#### Neo4jへの接続確認

```bash
# Makefileを使用する場合
make shell-neo4j

# 手動で接続する場合
docker compose exec neo4j cypher-shell -u neo4j -p password123

# Neo4j shellが開いたら
neo4j@neo4j> RETURN 'Hello, Graphiti!' as message;
neo4j@neo4j> :exit
```

#### Graphiti MCP APIの確認

```bash
# ヘルスチェック
curl http://localhost:30547/health

# 検索APIのテスト（空のクエリ）
curl -X POST http://localhost:30547/graph/search \
  -H "Content-Type: application/json" \
  -d '{"query": "", "limit": 5}' | python3 -m json.tool
```

#### フロントエンドUIの確認

ブラウザで http://localhost:20002 にアクセスして、UIが表示されることを確認します。

## 環境変数の設定

`.env`ファイルで設定可能な環境変数の詳細です。

### 必須の環境変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `OPENAI_API_KEY` | OpenAI APIキー | `sk-proj-xxxxxxxxxxxx` |

### Neo4j関連

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `NEO4J_USER` | `neo4j` | Neo4jユーザー名 |
| `NEO4J_PASSWORD` | `password123` | Neo4jパスワード |
| `NEO4J_HTTP_PORT` | `20474` | Neo4j HTTPポート（ホスト側） |
| `NEO4J_BOLT_PORT` | `20687` | Neo4j Boltポート（ホスト側） |
| `NEO4J_HEAP_INITIAL_SIZE` | `512M` | Neo4jヒープ初期サイズ |
| `NEO4J_HEAP_MAX_SIZE` | `1G` | Neo4jヒープ最大サイズ |
| `NEO4J_PAGECACHE_SIZE` | `512M` | Neo4jページキャッシュサイズ |

### OpenAI/LLM関連

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `OPENAI_MODEL` | `gpt-4o-mini` | 使用するOpenAIモデル |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` | OpenAI APIベースURL |
| `SEMAPHORE_LIMIT` | `10` | 並列処理数の制限（レート制限対策） |

### サービスポート

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `GRAPHITI_MCP_PORT` | `30547` | Graphiti MCPサーバーポート |
| `BACKEND_PORT` | `20001` | バックエンドAPIポート |
| `FRONTEND_PORT` | `20002` | フロントエンドUIポート |
| `MINIO_API_PORT` | `20734` | MinIO APIポート |
| `MINIO_CONSOLE_PORT` | `20735` | MinIOコンソールポート |

### MinIO関連

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `MINIO_ROOT_USER` | `minio` | MinIOルートユーザー |
| `MINIO_ROOT_PASSWORD` | `miniosecret` | MinIOルートパスワード |

### その他

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `CORS_ORIGINS` | `http://localhost:20002,...` | CORS許可オリジン |
| `GRAPHITI_TELEMETRY_ENABLED` | `false` | Graphitiテレメトリの有効化 |

## データ取り込み

Graphiti MCPに各種データソースからデータを取り込む方法を説明します。

### GitHub Issuesの取り込み

GitHub Issuesを取り込むには、GitHub Personal Access Tokenが必要です。

#### 1. GitHub Tokenの取得

1. GitHubにログイン
2. Settings → Developer settings → Personal access tokens → Tokens (classic)
3. "Generate new token (classic)" をクリック
4. スコープで `repo` を選択
5. トークンを生成してコピー

#### 2. 取り込み実行

```bash
# Makefileを使用する場合
make ingest-github \
  GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  GITHUB_OWNER=uniQorn-org \
  GITHUB_REPO=uniqorn-zoom

# 手動で実行する場合
docker compose exec -e GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  -e GITHUB_OWNER=uniQorn-org \
  -e GITHUB_REPO=uniqorn-zoom \
  graphiti-mcp python src/ingest_github.py
```

オプション：
- `--max-issues N`: 最大N件のissuesを取り込む
- `--state open|closed|all`: 取り込むissuesの状態（デフォルト: `all`）
- `--no-translate`: 英語翻訳を無効化

### Slackメッセージの取り込み

Slackメッセージを取り込むには、Slack User Token（`xoxc-`で始まる）が必要です。

#### 1. Slack Tokenの取得

1. Slackにブラウザでログイン
2. 開発者ツールを開く（F12）
3. Networkタブでリクエストを確認
4. リクエストヘッダーから`Authorization: Bearer xoxc-...`を見つける

#### 2. Workspace IDとChannel IDの確認

- ブラウザでSlackを開き、URLを確認: `https://app.slack.com/client/{WORKSPACE_ID}/{CHANNEL_ID}`

#### 3. 取り込み実行

```bash
# Makefileを使用する場合（過去7日分）
make ingest-slack \
  SLACK_TOKEN=xoxc-xxxxxxxxxxxx \
  WORKSPACE_ID=T09HNJQG1JA \
  CHANNEL_ID=C09JQQMUHCZ \
  DAYS=7

# 手動で実行する場合
docker compose exec -e SLACK_TOKEN=xoxc-xxxxxxxxxxxx \
  graphiti-mcp python src/ingest_slack.py \
  --token xoxc-xxxxxxxxxxxx \
  --workspace-id T09HNJQG1JA \
  --channel-id C09JQQMUHCZ \
  --days 7
```

オプション：
- `--days N`: 過去N日分のメッセージを取り込む（デフォルト: 7）
- `--no-translate`: 英語翻訳を無効化

### Zoom文字起こしの取り込み

Zoom会議の文字起こし（VTTファイル）を取り込みます。

#### 1. VTTファイルの配置

Zoom文字起こしファイル（`.vtt`）を`data/zoom/`ディレクトリに配置します：

```bash
cp /path/to/meeting_transcript.vtt data/zoom/
```

#### 2. 取り込み実行

```bash
# Makefileを使用する場合
make ingest-zoom

# 手動で実行する場合
docker compose exec graphiti-mcp python src/ingest_zoom.py --zoom-dir data/zoom
```

オプション：
- `--no-translate`: 英語翻訳を無効化

## Makefileコマンド一覧

プロジェクトで使用可能な便利なMakefileコマンドの一覧です。

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
make logs-minio    # MinIOのログ
```

### データ取り込み

```bash
make ingest-github GITHUB_TOKEN=xxx GITHUB_OWNER=xxx GITHUB_REPO=xxx
make ingest-slack SLACK_TOKEN=xxx WORKSPACE_ID=xxx CHANNEL_ID=xxx DAYS=7
make ingest-zoom
```

### データベース操作

```bash
make shell-neo4j      # Neo4j Cypherシェルを開く
make shell-mcp        # MCPコンテナのシェルを開く
make query-episodes   # エピソードを一覧表示
make query-entities   # エンティティを一覧表示
make query-facts      # Factsを一覧表示
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

### ビルド

```bash
make build         # Dockerイメージをビルド
make rebuild       # キャッシュなしでリビルド
```

### クイックコマンド

```bash
make quick-start   # setup + start + health check
make dev           # start + logs（開発用）
```

## トラブルシューティング

### 問題1: Neo4jが起動しない

**症状**: Neo4jコンテナが`unhealthy`状態になる

**原因**: メモリ不足

**解決方法**:

`.env`ファイルでメモリ設定を調整：

```env
NEO4J_HEAP_INITIAL_SIZE=256M
NEO4J_HEAP_MAX_SIZE=512M
NEO4J_PAGECACHE_SIZE=256M
```

または、docker-compose.ymlを直接編集して再起動：

```bash
make restart
```

### 問題2: OpenAI APIのレート制限エラー（429）

**症状**: データ取り込み時に429エラーが発生

**原因**: APIリクエストが多すぎる

**解決方法**:

`.env`ファイルで並列度を調整：

```env
# OpenAI Tierに応じて調整
# Tier 1 (無料): 1-2
# Tier 2: 5-8
# Tier 3: 10-15
# Tier 4: 20-50
SEMAPHORE_LIMIT=5
```

サービスを再起動：

```bash
make restart
```

### 問題3: ポートが既に使用されている

**症状**: `Error: bind: address already in use`

**原因**: 他のプロセスが同じポートを使用している

**解決方法**:

`.env`ファイルでポート番号を変更：

```env
NEO4J_HTTP_PORT=7475
NEO4J_BOLT_PORT=7688
GRAPHITI_MCP_PORT=30548
BACKEND_PORT=20003
FRONTEND_PORT=20004
```

### 問題4: データが表示されない

**症状**: 検索しても結果が返ってこない

**確認手順**:

1. **サービスの健全性を確認**:
   ```bash
   make health
   ```

2. **Neo4jにデータが存在するか確認**:
   ```bash
   make query-episodes
   make query-facts
   ```

3. **ログを確認**:
   ```bash
   make logs-mcp
   ```

4. **データを再取り込み**:
   ```bash
   # 既存データをクリア（警告: データが失われます）
   make clean-data
   make start

   # データを再取り込み
   make ingest-github GITHUB_TOKEN=xxx GITHUB_OWNER=xxx GITHUB_REPO=xxx
   ```

### 問題5: コンテナが起動しない

**症状**: `docker compose up`でエラーが発生

**確認手順**:

1. **Dockerが起動しているか確認**:
   ```bash
   docker ps
   ```

2. **ログを確認**:
   ```bash
   docker compose logs
   ```

3. **古いコンテナとボリュームを削除**:
   ```bash
   make clean-data
   ```

4. **イメージを再ビルド**:
   ```bash
   make rebuild
   make start
   ```

### 問題6: .envファイルが読み込まれない

**症状**: 環境変数が設定されていないエラー

**確認手順**:

1. **.envファイルが存在するか確認**:
   ```bash
   ls -la .env
   ```

2. **.envファイルの内容を確認**:
   ```bash
   cat .env
   ```

3. **必須の変数が設定されているか確認**:
   ```bash
   grep OPENAI_API_KEY .env
   ```

4. **再セットアップ**:
   ```bash
   make setup
   # .envを編集
   make start
   ```

## サポート

問題が解決しない場合は、以下の情報を含めてIssueを作成してください：

1. 実行したコマンド
2. エラーメッセージ
3. `docker compose logs`の出力
4. OSとDockerのバージョン
5. `.env`ファイルの内容（APIキーは除く）

GitHubリポジトリ: https://github.com/uniQorn-org/graphiti

## 次のステップ

セットアップが完了したら：

1. [README.md](README.md)で機能の詳細を確認
2. [データ取り込み](#データ取り込み)セクションでデータを追加
3. http://localhost:20002 でUIを試す
4. [REST API](server/docs/REST_API.md)でプログラマティックなアクセスを試す

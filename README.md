# Graphiti MCP - Real-Time Knowledge Graph Server

Graphiti MCPは、[Graphiti](https://github.com/getzep/graphiti)を使用した時間情報付きナレッジグラフの自動構築・更新システムです。Neo4jとOpenAI APIを組み合わせ、動的に変化するデータからリアルタイムに知識グラフを生成し、ハイブリッド検索（埋め込み + BM25 + グラフ探索）で素早く情報を取得できます。

## 特徴

- **リアルタイム増分更新**: 新規データ（エピソード）を即座に反映
- **二重時間モデル**: 出来事の発生時刻と取り込み時刻を別トラックで管理
- **ハイブリッド検索**: 埋め込み・BM25・グラフトラバーサルを組み合わせた高度な検索
- **柔軟なオントロジー**: Pydanticで独自のエンティティ/エッジ型を定義可能
- **MCPサーバー**: Model Context Protocol対応で、Claude DesktopやCursorから利用可能
- **REST API**: FastAPIベースのHTTP APIでプログラマティックにアクセス可能

## 必要な環境

- Docker & Docker Compose
- Python 3.12+ (開発時)
- OpenAI API Key

## クイックスタート

### 1. リポジトリのクローン

```bash
git clone https://github.com/uniQorn-org/graphiti.git
cd graphiti
```

### 2. 環境変数の設定

`.env`ファイルを作成し、OpenAI APIキーを設定:

```bash
cp .env.example .env
# .envファイルを編集してOPENAI_API_KEYを設定
```

必須の環境変数:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Docker Composeで起動

```bash
docker-compose up -d
```

起動するサービス:
- **neo4j**: Neo4j 5.26.16 (APOCプラグイン付き)
  - Browser UI: http://localhost:7474
  - Bolt: bolt://localhost:7687
  - ユーザー名: `neo4j`
  - パスワード: `password123`
- **graphiti-mcp**: Graphiti MCPサーバー
  - MCP Endpoint: http://localhost:8001/mcp/
- **search-bot-backend**: 社内検索Bot API (FastAPI + LangChain)
  - API Endpoint: http://localhost:20001/api
  - Docs: http://localhost:20001/docs
- **search-bot-frontend**: 社内検索Bot UI (React)
  - Web UI: http://localhost:20002

### 4. 動作確認

#### Neo4jブラウザで確認
http://localhost:7474 にアクセスし、認証情報でログイン:
- ユーザー名: `neo4j`
- パスワード: `password123`

#### MCP APIで確認
```bash
curl http://localhost:8001/mcp/
```

## 使用方法

### 1. MCPサーバーとして使用 (Claude Desktop/Cursor)

Claude DesktopやCursorの設定ファイルに以下を追加:

```json
{
  "mcpServers": {
    "graphiti": {
      "url": "http://localhost:8001/mcp/",
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

Graphiti MCPサーバーはFastAPIベースのREST APIを提供しています。詳細は[server/docs/REST_API.md](server/docs/REST_API.md)を参照してください。

## プロジェクト構造

```
graphiti/
├── client/              # Pythonクライアント
│   └── graphiti_client.py
├── server/              # MCPサーバー
│   ├── src/            # サーバーソースコード
│   │   ├── config/    # 設定管理
│   │   ├── models/    # データモデル
│   │   ├── routers/   # APIルーター
│   │   ├── services/  # ビジネスロジック
│   │   └── utils/     # ユーティリティ
│   ├── scripts/       # スクリプト（データローダー等）
│   └── slack_data/    # サンプルデータ
├── tests/              # テストファイル
├── docs/               # ドキュメント
├── docker-compose.yml  # Docker設定
├── Dockerfile          # MCPサーバーのDockerfile
├── pyproject.toml      # Python依存関係
├── .env.example        # 環境変数テンプレート
└── README.md
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
docker-compose up -d

# テスト実行
python tests/test_graphiti.py
```

### ログの確認

```bash
# 全サービスのログ
docker-compose logs -f

# Graphiti MCPのみ
docker-compose logs -f graphiti-mcp

# Neo4jのみ
docker-compose logs -f neo4j
```

## トラブルシューティング

### Neo4jが起動しない

メモリ設定を調整:
```yaml
# docker-compose.yml
environment:
  NEO4J_dbms_memory_heap_max__size: "512M"  # 1G → 512Mに減らす
```

### レート制限エラー (429)

`.env`ファイルで並列度を調整:
```env
SEMAPHORE_LIMIT=5  # デフォルトは10
```

OpenAI APIのTierに応じて調整:
- Tier 1 (無料): 1-2
- Tier 2: 5-8
- Tier 3: 10-15
- Tier 4: 20-50

### コンテナの再起動

```bash
# 全サービス停止
docker-compose down

# データも削除して初期化
docker-compose down -v

# 再起動
docker-compose up -d
```

## 社内検索Bot

### 概要

LangChain + Graphitiを使った対話型社内検索システムです。

### 主な機能

1. **AIチャット**
   - 自然言語で質問すると、ナレッジグラフを検索して回答
   - チャット履歴を保持
   - 検索結果を可視化

2. **手動検索**
   - キーワードでナレッジグラフを直接検索
   - エンティティと関係性を表示

3. **Fact編集**
   - 検索結果から間違った情報を発見
   - クリックで修正可能
   - 修正理由を記録

### 使い方

1. **起動**
   ```bash
   docker-compose up -d
   ```

2. **アクセス**
   - フロントエンド: http://localhost:20002
   - バックエンドAPI: http://localhost:20001/docs

3. **チャットで質問**
   - 「山田さんの役割は？」などと入力
   - AIが検索結果をもとに回答
   - 右パネルに関連Factsが表示

4. **Factを修正**
   - 表示されたFactの「修正」ボタンをクリック
   - 新しいFactを入力して保存

5. **手動検索**
   - 「検索」タブに切り替え
   - キーワードを入力して検索

### アーキテクチャ

```
[React Frontend] (Port 20002)
      ↓ REST API
[FastAPI Backend] (Port 20001)
      ↓ LangChain
[Graphiti Core]
      ↓
[Neo4j] (Port 7687)
```

### 詳細ドキュメント

- [バックエンド README](backend/README.md)
- [フロントエンド README](frontend/README.md)

## 関連ドキュメント

- [Graphiti公式ドキュメント](https://help.getzep.com/graphiti/)
- [Graphiti解説 (日本語)](docs/graphiti.md)
- [REST API仕様](server/docs/REST_API.md)
- [Neo4j設定ガイド](https://neo4j.com/docs/)

## ライセンス

Apache-2.0

## コントリビューション

Issue・Pull Requestを歓迎します！

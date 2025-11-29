# Graphiti システムアーキテクチャ

> **Version**: 1.0
> **Last Updated**: 2025-11-29

このドキュメントは、Graphitiシステムの全体的なアーキテクチャと各コンポーネントの役割を説明します。

## 目次

- [概要](#概要)
- [3層分離アーキテクチャ](#3層分離アーキテクチャ)
- [各層の詳細](#各層の詳細)
- [通信フロー](#通信フロー)
- [Docker構成](#docker構成)
- [ポート番号とサービス一覧](#ポート番号とサービス一覧)
- [データフロー](#データフロー)
- [スケーラビリティと負荷分散](#スケーラビリティと負荷分散)

---

## 概要

Graphitiシステムは、**完全に分離された3層アーキテクチャ**を採用しています。各層は独立したDockerコンテナとして動作し、HTTP/MCPプロトコルで通信します。

この設計により：
- **関心の分離**: 各層が明確な責務を持つ
- **独立したスケーリング**: 各層を個別にスケールアウト可能
- **保守性の向上**: 各層を独立して開発・テスト可能
- **再利用性**: MCPサーバーは他のクライアントからも利用可能

---

## 3層分離アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                 外部データソース                              │
│   (GitHub Issues, Slack Messages, Zoom Transcripts)          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│               Layer 3: Data Ingestion                        │
│          (server/src/ingestion/*.py)                         │
│                                                              │
│  • GitHub Issues Ingester                                   │
│  • Slack Messages Ingester                                  │
│  • Zoom Transcripts Ingester                                │
│  • Custom Data Source Ingesters                             │
│                                                              │
│  実行方法: スタンドアロンスクリプト                          │
│  接続方法: MCPClient経由でGraphiti MCPを呼び出し            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ↓ HTTP/MCP
┌─────────────────────────────────────────────────────────────┐
│           Layer 1: Graphiti MCP Server                       │
│         (server/src/graphiti_mcp_server.py)                  │
│                                                              │
│  コンテナ: graphiti-mcp                                      │
│  ポート: 30547 (http://graphiti-mcp:8001)                   │
│                                                              │
│  【責務】                                                    │
│  • Graphitiコア機能の提供                                   │
│  • Neo4jデータベースへの直接アクセス                        │
│  • エピソード処理のキュー管理                                │
│  • エンティティ抽出とグラフ構築                              │
│                                                              │
│  【提供API】                                                │
│  • add_memory (エピソード追加)                              │
│  • search_memory_facts (Fact検索)                           │
│  • search_nodes (ノード検索)                                │
│  • update_fact (Fact更新)                                   │
│  • delete_episode (エピソード削除)                          │
│  • clear_graph (グラフクリア)                               │
│  • get_citation_chain (引用チェーン取得)                    │
│                                                              │
│  【使用技術】                                                │
│  • graphiti-core (Apache 2.0)                               │
│  • FastMCP (MCPサーバーフレームワーク)                      │
│  • Neo4j Driver (データベース接続)                          │
│  • OpenAI API (LLM、エンティティ抽出)                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ↓ Neo4j Bolt Protocol (Port 20687)
┌─────────────────────────────────────────────────────────────┐
│                    Neo4j Database                            │
│                                                              │
│  コンテナ: graphiti-search-bot-neo4j                         │
│  ポート: 20474 (HTTP), 20687 (Bolt)                         │
│                                                              │
│  【データ構造】                                              │
│  • Nodes: Episodic (エピソード), Entity (エンティティ)      │
│  • Edges: RELATES_TO (関係), MENTIONS (参照)                │
│  • Properties: メタデータ、埋め込みベクトル                 │
└─────────────────────────────────────────────────────────────┘
                           ↑
                           │ HTTP (MCPClientService経由)
┌─────────────────────────────────────────────────────────────┐
│              Layer 2: Chat Backend                           │
│              (backend/src/main.py)                           │
│                                                              │
│  コンテナ: search-bot-backend                                │
│  ポート: 20001 (http://search-bot-backend)                  │
│                                                              │
│  【責務】                                                    │
│  • チャット機能とビジネスロジック                            │
│  • LangChainベースのRAG処理                                 │
│  • ユーザーリクエストの処理                                  │
│  • GraphitiへのプロキシAPI提供                              │
│                                                              │
│  【提供API】                                                │
│  • POST /api/chat (チャット)                                │
│  • POST /api/search (手動検索)                              │
│  • PUT /api/facts/{uuid} (Fact更新)                         │
│  • POST /api/episodes (エピソード追加)                      │
│  • GET /health (ヘルスチェック)                             │
│                                                              │
│  【使用技術】                                                │
│  • FastAPI (Webフレームワーク)                              │
│  • LangChain (RAGフレームワーク)                            │
│  • MCPClientService (Graphiti MCP通信)                      │
│  • OpenAI API (LLM、チャット生成)                           │
└─────────────────────────────────────────────────────────────┘
                           ↑
                           │ HTTP
┌─────────────────────────────────────────────────────────────┐
│                 Frontend (React + Vite)                      │
│                                                              │
│  コンテナ: search-bot-frontend                               │
│  ポート: 20002                                              │
│                                                              │
│  【機能】                                                    │
│  • チャットUI                                               │
│  • 検索結果表示                                              │
│  • Fact編集UI                                               │
│  • グラフ可視化                                              │
└─────────────────────────────────────────────────────────────┘
                           ↑
                           │ HTTP
                      ユーザー
```

---

## 各層の詳細

### Layer 1: Graphiti MCP Server

**ファイル**: [server/src/graphiti_mcp_server.py](../server/src/graphiti_mcp_server.py)

#### 主要機能

1. **エピソード処理**
   - QueueServiceによる順次処理（group_id毎）
   - レート制限対策（SEMAPHORE_LIMIT）
   - リトライロジック（429エラー時）

2. **グラフ操作**
   - Neo4jへの直接クエリ実行
   - インデックス・制約の管理
   - グラフデータのCRUD操作

3. **プロトコル**
   - MCP (Model Context Protocol): Claude Desktop等との連携
   - REST API: HTTP経由での直接アクセス
   - Streamable HTTP: 非同期ストリーミング

#### クラス構造

```python
class GraphitiService:
    """Graphitiサービスのメインクラス"""

    def __init__(self, config: GraphitiConfig, semaphore_limit: int = 10):
        self.config = config
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.client: Graphiti | None = None
        self.entity_types = None

    async def initialize(self) -> None:
        """LLM、embedder、databaseクライアントを初期化"""
        # LLMClientFactory、EmbedderFactory、DatabaseDriverFactoryを使用
        # graphiti-coreのGraphitiクライアントを初期化
        # インデックスと制約を構築

    async def get_client(self) -> Graphiti:
        """初期化済みGraphitiクライアントを取得"""
```

#### 設定管理

```yaml
# config/config.yaml
llm:
  provider: "openai"
  model: "gpt-4o-mini"
  temperature: 0.0

embedder:
  provider: "openai"
  model: "text-embedding-3-small"

database:
  provider: "neo4j"
  uri: "bolt://neo4j:7687"
  user: "neo4j"
  password: "password123"

graphiti:
  group_id: "default"
  entity_types:
    - name: "Requirement"
      description: "要件を表すエンティティ"
```

---

### Layer 2: Chat Backend

**ファイル**: [backend/src/main.py](../backend/src/main.py)

#### 主要機能

1. **チャット処理**
   - LangChainによるRAG実装
   - Graphiti検索結果の統合
   - コンテキスト管理

2. **MCPクライアント**
   - HTTPクライアント経由でGraphiti MCPに接続
   - Neo4jに**直接接続しない**
   - エラーハンドリングとリトライ

3. **ビジネスロジック**
   - ユーザーリクエストの検証
   - レスポンスのフォーマット
   - CORS設定

#### クラス構造

```python
class MCPClientService:
    """Graphiti MCPサーバーとHTTP通信するクライアント"""

    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)

    async def search(self, query: str, limit: int = 10) -> SearchResult:
        """MCP経由でナレッジグラフを検索"""
        url = f"{self.mcp_url}/graph/search"
        payload = {
            "query": query,
            "search_type": "facts",
            "max_results": limit,
        }
        response = await self.client.post(url, json=payload)
        # レスポンスをSearchResultに変換

class LangChainService:
    """LangChainベースのチャットサービス"""

    def __init__(self, graphiti_service: MCPClientService, openai_api_key: str):
        self.graphiti = graphiti_service
        self.llm = ChatOpenAI(api_key=openai_api_key)

    async def chat(self, message: str, history: List[ChatMessage]) -> ChatResponse:
        """Graphiti検索結果を使用してチャット応答を生成"""
        # 1. Graphitiで検索
        search_results = await self.graphiti.search(message)
        # 2. 検索結果をコンテキストに変換
        # 3. LLMで応答生成
```

---

### Layer 3: Data Ingestion

**ディレクトリ**: [server/src/ingestion/](../server/src/ingestion/)

#### 主要機能

1. **データソース連携**
   - GitHub API連携（Issues, Pull Requests）
   - Slack API連携（Messages, Threads）
   - Zoom API連携（Transcripts）
   - カスタムデータソース対応

2. **データ変換**
   - 生データをEpisode形式に変換
   - メタデータの抽出と整形
   - source_urlの埋め込み

3. **バッチ処理**
   - 並列処理の制御
   - プログレスバー表示
   - エラーハンドリング

#### 基底クラス

```python
class BaseIngester(ABC):
    """すべてのデータ取り込みの基底クラス"""

    def __init__(
        self,
        mcp_url: str = "http://localhost:8001/mcp/",
        translate: bool = True,
        save_to_disk: bool = True,
    ):
        self.mcp_url = mcp_url
        self.translate = translate
        self.mcp_client = MCPClient(mcp_url)

    @abstractmethod
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """データソースからデータを取得"""
        pass

    @abstractmethod
    def build_episode(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """生データをエピソード形式に変換"""
        pass

    async def ingest(self, clear_existing: bool = False) -> Dict[str, Any]:
        """取り込みパイプラインを実行"""
        # 1. データ取得
        data = await self.fetch_data()
        # 2. ディスクに保存（オプション）
        if self.save_to_disk:
            self.save_data(data)
        # 3. MCPクライアント経由で投入
        for item in data:
            episode = self.build_episode(item)
            await self.mcp_client.add_episode(session, **episode)
```

#### 実装例: GitHub Ingester

```python
class GitHubIngester(BaseIngester):
    """GitHub Issues取り込み"""

    def get_source_type(self) -> str:
        return "github"

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """GitHub APIからIssuesを取得"""
        # GitHub APIクライアントを使用
        # Issuesとコメントを取得

    def build_episode(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """IssueをEpisode形式に変換"""
        return {
            "name": f"github_issue_{issue['number']}",
            "episode_body": issue["body"],
            "source": "text",
            "source_description": f"GitHub Issue #{issue['number']}",
            "source_url": issue["html_url"],  # 重要: source_urlを指定
        }
```

---

## 通信フロー

### 1. ユーザーチャットフロー

```
ユーザー
  ↓ (1) HTTP POST /api/chat
Frontend (React)
  ↓ (2) HTTP POST http://localhost:20001/api/chat
Chat Backend (FastAPI)
  ↓ (3) LangChainService.chat()
  ↓ (4) MCPClientService.search()
  ↓ (5) HTTP POST http://graphiti-mcp:8001/graph/search
Graphiti MCP Server
  ↓ (6) Neo4j Cypher Query
  ↓     MATCH (n)-[r]->(m) WHERE ...
Neo4j Database
  ↑ (7) 検索結果 (Nodes, Edges)
Graphiti MCP Server
  ↑ (8) JSON Response (Facts with Citations)
Chat Backend
  ↓ (9) LLM.generate(context + user_message)
  ↓     OpenAI API呼び出し
OpenAI
  ↑ (10) AI生成の回答
Chat Backend
  ↑ (11) ChatResponse JSON
Frontend
  ↑ (12) 画面に表示
ユーザー
```

### 2. データ取り込みフロー

```
GitHub API
  ↓ (1) Issues取得
GitHubIngester
  ↓ (2) Episode変換
  ↓     - name: github_issue_123
  ↓     - source_url: https://github.com/...
  ↓ (3) MCPClient.add_episode()
  ↓ (4) HTTP POST http://graphiti-mcp:8001/mcp/
  ↓     MCP add_memory tool
Graphiti MCP Server
  ↓ (5) QueueService.add_episode()
  ↓     - group_id毎のキューに追加
  ↓     - 順次処理開始
  ↓ (6) graphiti-core add_episode()
  ↓     - LLMでエンティティ抽出
  ↓     - source_url埋め込み
  ↓ (7) Neo4j CREATE/MERGE
Neo4j Database
  ↑ (8) 完了通知
Graphiti MCP Server
  ↑ (9) Success Response
GitHubIngester
  ↑ (10) 次のIssue処理へ
```

---

## Docker構成

### docker-compose.yml

```yaml
services:
  # データベース
  neo4j:
    image: neo4j:5.26.16
    ports:
      - "20474:7474"  # HTTP
      - "20687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/password123
      NEO4JLABS_PLUGINS: '["apoc"]'

  # MCPサーバー
  graphiti-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "30547:8001"
    depends_on:
      - neo4j
    environment:
      NEO4J_URI: bolt://neo4j:7687

  # チャットバックエンド
  search-bot-backend:
    build:
      context: ./backend
    ports:
      - "20001:20001"
    depends_on:
      - neo4j
    environment:
      GRAPHITI_MCP_URL: http://graphiti-mcp:8001

  # フロントエンド
  search-bot-frontend:
    build:
      context: ./frontend
    ports:
      - "20002:20002"
    depends_on:
      - search-bot-backend
    environment:
      VITE_API_BASE_URL: http://localhost:30547

  # オブジェクトストレージ (Zoom文字起こし用)
  minio:
    image: minio/minio:latest
    ports:
      - "20734:9000"   # API
      - "20735:9001"   # Console
    command: server /data --console-address ":9001"
```

---

## ポート番号とサービス一覧

| サービス | ポート | プロトコル | 説明 |
|---------|-------|----------|------|
| Neo4j HTTP | 20474 | HTTP | Neo4j ブラウザUI |
| Neo4j Bolt | 20687 | Bolt | Neo4j データベース接続 |
| Graphiti MCP | 30547 | HTTP/MCP | MCPサーバーエンドポイント |
| Chat Backend | 20001 | HTTP | チャットAPI |
| Frontend | 20002 | HTTP | WebUI |
| MinIO API | 20734 | HTTP | オブジェクトストレージAPI |
| MinIO Console | 20735 | HTTP | MinIO管理UI |

### 内部通信

- `graphiti-mcp` → `neo4j:7687` (Bolt)
- `search-bot-backend` → `graphiti-mcp:8001` (HTTP)
- `search-bot-frontend` → `search-bot-backend:20001` (HTTP)

### 外部アクセス

- ユーザー → `localhost:20002` (Frontend)
- Neo4j Browser → `localhost:20474`
- MinIO Console → `localhost:20735`

---

## データフロー

### エピソード追加のデータフロー

```
1. クライアント
   ↓ EpisodeCreateRequest
   {
     "name": "slack_msg_123",
     "content": "プロジェクトの進捗報告",
     "source": "message",
     "source_url": "https://slack.com/archives/..."
   }

2. Graphiti MCP Server (Queue)
   ↓ source_url埋め込み
   {
     "name": "slack_msg_123",
     "episode_body": "プロジェクトの進捗報告",
     "source_description": "Slackメッセージ, source_url: https://slack.com/..."
   }

3. graphiti-core (エンティティ抽出)
   ↓ LLM処理
   Entities:
   - {name: "プロジェクトA", type: "Organization"}
   - {name: "進捗報告", type: "Document"}

   Facts:
   - {source: "プロジェクトA", target: "進捗報告", fact: "..."}

4. Neo4j (永続化)
   ↓ Cypher CREATE/MERGE
   Nodes:
   - (e:Episodic {uuid: "...", name: "slack_msg_123"})
   - (n1:Entity {uuid: "...", name: "プロジェクトA", labels: ["Organization"]})
   - (n2:Entity {uuid: "...", name: "進捗報告", labels: ["Document"]})

   Edges:
   - (e)-[:MENTIONS]->(n1)
   - (e)-[:MENTIONS]->(n2)
   - (n1)-[:RELATES_TO {fact: "...", episodes: ["..."]}]->(n2)
```

### 検索のデータフロー

```
1. ユーザークエリ
   "プロジェクトAの進捗は?"

2. Graphiti MCP Server (Hybrid Search)
   ↓ Embedding生成
   query_embedding = OpenAI.embed("プロジェクトAの進捗は?")

   ↓ Neo4j Hybrid Search
   - Vector Search (embedding類似度)
   - BM25 Search (キーワードマッチ)
   - Graph Traversal (関連ノード探索)

   ↓ RRF (Reciprocal Rank Fusion)
   - 各検索結果をマージ・スコアリング

3. Citation Service (引用情報取得)
   ↓ For each Edge
   - episodes配列からEpisode UUIDを取得
   - source_descriptionからsource_url抽出
   - CitationInfo構築

4. レスポンス
   [
     {
       "uuid": "edge_123",
       "fact": "プロジェクトAは順調に進捗している",
       "source_node_name": "プロジェクトA",
       "target_node_name": "進捗報告",
       "citations": [
         {
           "episode_name": "slack_msg_123",
           "source_url": "https://slack.com/...",
           "created_at": "2025-11-25T14:30:00Z"
         }
       ]
     }
   ]
```

---

## スケーラビリティと負荷分散

### 垂直スケーリング

各コンポーネントのリソース調整:

```yaml
# docker-compose.yml
services:
  graphiti-mcp:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  neo4j:
    environment:
      NEO4J_dbms_memory_heap_max__size: 4G
      NEO4J_dbms_memory_pagecache_size: 2G
```

### 水平スケーリング

#### MCPサーバーの複製

```yaml
services:
  graphiti-mcp-1:
    # ... 設定 ...
    ports:
      - "30547:8001"

  graphiti-mcp-2:
    # ... 設定 ...
    ports:
      - "30548:8001"

  nginx:
    image: nginx:latest
    ports:
      - "8001:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - graphiti-mcp-1
      - graphiti-mcp-2
```

```nginx
# nginx.conf
upstream graphiti_mcp {
    least_conn;
    server graphiti-mcp-1:8001;
    server graphiti-mcp-2:8001;
}

server {
    listen 80;
    location / {
        proxy_pass http://graphiti_mcp;
    }
}
```

### レート制限対策

```python
# 環境変数で調整
SEMAPHORE_LIMIT=10  # 同時実行エピソード数
EPISODE_PROCESSING_DELAY=20  # エピソード間の遅延（秒）

# QueueServiceの設定
# - group_id毎に独立したキュー
# - 順次処理でレート制限を回避
# - 429エラー時は指数バックオフでリトライ
```

---

## 参考資料

- [メタデータ仕様書](./METADATA_SPECIFICATION.md)
- [データ取り込みガイド](./DATA_INGESTION.md)
- [graphiti-core GitHub](https://github.com/getzep/graphiti)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

---

## バージョン履歴

- **1.1** (2025-11-29): コード品質改善反映
  - Phase 5-7のリファクタリング結果を反映
  - GraphitiServiceのモジュール化（services/graphiti_service_mcp.py）
  - CORSミドルウェアの分離（middleware/cors.py）
  - QueueServiceのデータクラス化（EpisodeProcessingConfig）

- **1.0** (2025-11-29): 初版作成
  - 3層アーキテクチャの説明
  - 各層の詳細
  - 通信フローとデータフロー
  - Docker構成
  - スケーラビリティガイド

# 自作 Graphiti MCP REST API Documentation

このドキュメントでは、自作Graphiti MCPで利用可能なREST APIエンドポイントについて説明します。

本Graphiti MCPは自作です。

MCPサーバー `server/src/graphiti_mcp_server.py`

FastMCPライブラリを使って実装。

MCPクライアント `server/src/client_example.py`

## ベースURL

```
http://localhost:8001
```

Docker Composeで起動している場合、上記のURLでアクセス可能です。

---

## エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| POST | `/graph/episodes` | Episode作成（メモリ追加） |
| POST | `/graph/search` | 統合検索（nodes/facts/episodes） |
| DELETE | `/graph/episodes/{uuid}` | Episode削除（関連Node/Factも削除） |
| PATCH | `/graph/facts/{uuid}` | Fact更新（修正・編集） |
| GET | `/health` | ヘルスチェック |

---

## 詳細仕様

### 1. エピソード追加

新しいエピソード（メモリ）をGraphitiに追加します。エピソードは非同期でバックグラウンド処理され、エンティティとリレーションが自動抽出されます。

**エンドポイント:** `POST /graph/episodes`

**リクエストボディ:**

```json
{
  "name": "Meeting Notes",
  "content": "Discussion about AI development and project planning",
  "group_id": "main",
  "source": "text",
  "source_description": "Team meeting notes",
  "uuid": "optional-uuid"
}
```

**パラメータ:**

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|-----------|------|
| `name` | string | ✅ | - | エピソードの名前 |
| `content` | string | ✅ | - | エピソードの内容・本文 |
| `group_id` | string | | [default] | グループID（未指定の場合はサーバーデフォルト） |
| `source` | string | | "text" | ソースタイプ: "text", "json", "message" |
| `source_description` | string | | "" | ソースの説明 |
| `uuid` | string | | null | カスタムUUID（オプション） |

**レスポンス例:**

```json
{
  "status": "success",
  "message": "Episode 'Meeting Notes' queued for processing in group 'main'",
  "episode_name": "Meeting Notes",
  "group_id": "main"
}
```

**使用例:**

```bash
# テキストエピソード追加
curl -X POST http://localhost:8001/graph/episodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Team Meeting 2025-01-15",
    "content": "Discussed Q1 roadmap. John will lead the AI project. Sarah is working on the API redesign.",
    "source": "text",
    "source_description": "Meeting minutes"
  }'

# JSONデータとして追加
curl -X POST http://localhost:8001/graph/episodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "User Profile",
    "content": "{\"name\": \"John Doe\", \"role\": \"Engineer\", \"skills\": [\"Python\", \"AI\"]}",
    "source": "json",
    "source_description": "CRM data export"
  }'
```

**注意事項:**

- エピソード追加は**非同期処理**です。APIは即座にレスポンスを返し、バックグラウンドでエンティティ抽出が行われます
- `source: "json"` を使用する場合、`content`はJSON文字列である必要があります
- 同じ`group_id`のエピソードは順次処理され、競合を回避します

---

### 2. グラフ検索 (統合検索)

ノード、Facts、エピソードを統合的に検索します。

**エンドポイント:** `POST /graph/search`

**リクエストボディ:**

```json
{
  "query": "検索クエリ",
  "search_type": "facts|nodes|episodes",
  "max_results": 10,
  "group_ids": ["group1", "group2"],
  "entity_types": ["Person", "Organization"],
  "center_node_uuid": "optional-uuid"
}
```

**パラメータ:**

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|-----------|------|
| `query` | string | ✅ | - | 検索クエリ文字列 |
| `search_type` | string | | "facts" | 検索タイプ: "facts", "nodes", "episodes" |
| `max_results` | integer | | 10 | 最大結果数（1-100） |
| `group_ids` | array[string] | | [default] | フィルタ対象のgroup ID |
| `entity_types` | array[string] | | null | ノード検索時のエンティティタイプフィルタ |
| `center_node_uuid` | string | | null | Fact検索時の中心ノードUUID |

**レスポンス例:**

```json
{
  "message": "Found 5 nodes",
  "search_type": "nodes",
  "results": [
    {
      "uuid": "8846b948-5ab2-4f49-b743-0c83f1741429",
      "name": "Agent",
      "labels": ["Entity"],
      "created_at": "2025-11-21T18:54:34.424693+00:00",
      "summary": "Agent development involves...",
      "group_id": "main",
      "attributes": {}
    }
  ],
  "count": 5
}
```

**使用例:**

```bash
# ノード検索
curl -X POST http://localhost:8001/graph/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "agent development",
    "search_type": "nodes",
    "max_results": 5
  }'

# Fact検索
curl -X POST http://localhost:8001/graph/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "relationship between agents",
    "search_type": "facts",
    "max_results": 10
  }'

# ノード検索
curl -X POST http://localhost:8001/graph/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "software engineer",
    "search_type": "nodes",
    "max_results": 5,
    "entity_types": ["Person"]
  }'

# エピソード一覧取得（空クエリで全件取得）
curl -X POST http://localhost:8001/graph/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "search_type": "episodes",
    "max_results": 10
  }'

# エピソード検索（キーワード指定）
curl -X POST http://localhost:8001/graph/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "meeting discussion",
    "search_type": "episodes",
    "max_results": 5
  }'
```

---

### 3. Episode削除

指定されたUUIDのEpisodeと、それに関連する全てのNode/Factを削除します。

**エンドポイント:** `DELETE /graph/episodes/{uuid}`

**パスパラメータ:**

| パラメータ | 型 | 説明 |
|-----------|------|------|
| `uuid` | string | 削除するEpisodeのUUID |

**レスポンス例:**

```json
{
  "status": "deleted",
  "uuid": "abc123...",
  "message": "Episode abc123... and related entities deleted successfully"
}
```

**使用例:**

```bash
# Episodeを削除（関連するNode/Factも削除される）
curl -X DELETE http://localhost:8001/graph/episodes/abc123-def456-ghi789
```

**削除される内容:**
- Episode自体（原データ）
- Episodeから抽出された全てのNode（エンティティ）
- それらのNodeに関連する全てのFact（関係性）

**ユースケース:**
- 誤って追加したデータを完全に削除
- テストデータの削除
- プライバシー保護のための個人情報削除
- 不要になった原データの削除

---

### 4. Fact更新（編集）

既存のFactを更新します。内部的には旧版を無効化し、新しいFactを作成します。

**エンドポイント:** `PATCH /graph/facts/{uuid}`

**パスパラメータ:**

| パラメータ | 型 | 説明 |
|-----------|------|------|
| `uuid` | string | 更新するFactのUUID |

**リクエストボディ:**

```json
{
  "fact": "新しいfact文",
  "source_node_uuid": "optional-source-uuid",
  "target_node_uuid": "optional-target-uuid",
  "attributes": {
    "custom_field": "custom_value"
  }
}
```

**パラメータ:**

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `fact` | string | ✅ | 新しいfact文/説明 |
| `source_node_uuid` | string | | ソースノードのUUID（変更する場合のみ） |
| `target_node_uuid` | string | | ターゲットノードのUUID（変更する場合のみ） |
| `attributes` | object | | 新しいFactに追加するカスタム属性 |

**レスポンス例:**

```json
{
  "status": "updated",
  "old_uuid": "abc123...",
  "new_uuid": "xyz789...",
  "message": "Fact updated successfully. Old fact abc123... expired, new fact xyz789... created"
}
```

**使用例:**

```bash
curl -X PATCH http://localhost:8001/graph/facts/abc123-def456 \
  -H "Content-Type: application/json" \
  -d '{
    "fact": "Updated relationship description",
    "attributes": {
      "confidence": 0.95,
      "source": "manual_edit"
    }
  }'
```

---

### 5. ヘルスチェック

サーバーの健全性を確認します。

**エンドポイント:** `GET /health`

**レスポンス例:**

```json
{
  "status": "healthy",
  "service": "graphiti-mcp"
}
```

**使用例:**

```bash
curl http://localhost:8001/health
```

---

## エラーハンドリング

すべてのエンドポイントは、エラー時に以下の形式のレスポンスを返します：

```json
{
  "error": "エラーメッセージ",
  "details": "詳細情報（オプション）",
  "status_code": 500
}
```

**ステータスコード:**

| コード | 意味 |
|-------|------|
| 200 | 成功 |
| 400 | 不正なリクエスト |
| 404 | リソースが見つからない |
| 500 | サーバーエラー |

---

## 認証

現在、REST APIには認証機能がありません。本番環境で使用する場合は、適切なアクセス制御を実装してください。

---

## フロントエンドからの使用例

### JavaScript (Fetch API)

```javascript
// グラフ検索
async function searchGraph(query, searchType = 'facts') {
  const response = await fetch('http://localhost:8001/graph/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: query,
      search_type: searchType,
      max_results: 10,
    }),
  });

  return await response.json();
}

// Episode削除
async function deleteEpisode(uuid) {
  const response = await fetch(`http://localhost:8001/graph/episodes/${uuid}`, {
    method: 'DELETE',
  });

  return await response.json();
}

// Fact更新
async function updateFact(uuid, newFactText) {
  const response = await fetch(`http://localhost:8001/graph/facts/${uuid}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      fact: newFactText,
    }),
  });

  return await response.json();
}

// 使用例
searchGraph('agent development', 'nodes')
  .then(data => console.log('Search results:', data));
```

### TypeScript + React例

```typescript
import { useState } from 'react';

interface SearchResult {
  message: string;
  search_type: string;
  results: any[];
  count: number;
}

function GraphSearchComponent() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult | null>(null);

  const handleSearch = async () => {
    const response = await fetch('http://localhost:8001/graph/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        search_type: 'nodes',
        max_results: 10,
      }),
    });

    const data = await response.json();
    setResults(data);
  };

  return (
    <div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search graph..."
      />
      <button onClick={handleSearch}>Search</button>

      {results && (
        <div>
          <p>{results.message}</p>
          <ul>
            {results.results.map((item) => (
              <li key={item.uuid}>{item.name}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

---

## トラブルシューティング

### CORS エラーが発生する

フロントエンドから直接APIを呼び出す場合、CORSエラーが発生する可能性があります。その場合は、`graphiti_mcp_server.py`でCORS設定を追加してください：

```python
from starlette.middleware.cors import CORSMiddleware

mcp.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に設定
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### サービスが初期化されていない

エラー `"Graphiti service not initialized"` が表示される場合、サーバーが完全に起動していません。ログを確認してください：

```bash
docker logs graphiti-mcp --tail 50
```

### 検索結果が空

- `group_ids`パラメータが正しいか確認
- データが実際にグラフに存在するか確認（MCPツールの`get_episodes`で確認可能）

---

## さらなる情報

- **MCPツール**: REST APIとは別に、MCPツール（`add_memory`, `search_nodes`など）も利用可能です
- **graphiti-core**: 内部で使用しているライブラリのドキュメント: https://github.com/getzep/graphiti

# Source URL Data Flow

このドキュメントは、ソースURL（リンク）がどのようにシステムを通じて流れるかを説明します。

## データフロー

```
データソース → Ingestion → MCP Server → Backend → Frontend
  (GitHub,      (scripts)    (graphiti)   (search)   (UI)
   Slack,
   Zoom)
```

## 1. データ取り込み (Ingestion)

### スクリプト: `server/src/scripts/ingest_*.py`

各データソースから取り込み、`source_url`を設定します：

```python
# GitHub example
source_url = "https://github.com/owner/repo/issues/123"

# Slack example
source_url = "https://app.slack.com/client/T.../C.../p1234567890"

# Zoom example
source_url = "http://localhost:20734/zoom-transcripts/uuid_transcript.vtt"
```

### MCP Client: `server/src/ingestion/mcp_client.py`

`add_episode()` メソッドで `source_url` パラメータを受け取ります。

### Queue Service: `server/src/services/queue_service.py:139-145`

⚠️ **重要**: `source_url`は`source_description`に埋め込まれます：

```python
if source_url:
    final_source_description = f"{source_description}, source_url: {source_url}"
```

理由: Graphiti Core の `EpisodicNode` には `source_url` フィールドがないため。

## 2. ストレージ (Neo4j)

### Episode ノードのプロパティ

```cypher
MATCH (e:Episodic) RETURN e.source_description
// 結果例:
// "GitHub issue #105, state: open, author: Tonoyama,
//  created: 2025-11-22T17:02:47+00:00,
//  source_url: https://github.com/uniQorn-org/uniqorn-zoom/issues/105"
```

## 3. 取得と抽出 (Citation Service)

### `server/src/services/citation_service.py:14-30`

`extract_source_url()` 関数が `source_description` から URL を抽出：

```python
def extract_source_url(source_description: str) -> str | None:
    match = re.search(r'source_url:\s*(https?://[^\s,]+)', source_description)
    if match:
        return match.group(1)
    return None
```

### `get_episode_citations()` 関数

エピソードから citations を取得し、各 citation に `source_url` を含めます：

```python
citation = CitationInfo(
    episode_uuid=episode_data.get("uuid", ""),
    episode_name=episode_data.get("name", ""),
    source=episode_data.get("source", "unknown"),
    source_description=source_desc,
    created_at=...,
    source_url=extract_source_url(source_desc),  # ← ここで抽出
)
```

## 4. 検索API (MCP Server)

### `server/src/routers/graph_api.py:106-240`

#### Facts 検索の場合:

```python
# 149-152行目
results = await asyncio.gather(*[
    format_fact_result(edge, client.driver) for edge in relevant_edges
])
```

`format_fact_result()` が各 edge の citations を取得します。

### `server/src/utils/formatting.py:33-66`

```python
async def format_fact_result(edge: EntityEdge, driver: Any = None):
    result = edge.model_dump(...)

    if driver:
        citations = await get_episode_citations(driver, edge.uuid, "edge")
        result["citations"] = citations  # ← citationsを追加

    return result
```

### レスポンス形式

```json
{
  "message": "Found 10 facts",
  "search_type": "facts",
  "results": [
    {
      "uuid": "...",
      "fact": "...",
      "citations": [
        {
          "episode_uuid": "...",
          "episode_name": "github:issue:owner/repo#123",
          "source": "text",
          "source_description": "GitHub issue #123, ..., source_url: https://...",
          "created_at": "2025-11-24T...",
          "source_url": "https://github.com/owner/repo/issues/123"
        }
      ]
    }
  ]
}
```

## 5. Backend API

### `backend/src/services/graphiti_service.py:51-184`

Backend の `search()` メソッドは：

1. Graphiti client で検索 (64行目)
2. 各 edge の citations を取得 (152-166行目)
3. `SearchResult` に citations を含めて返す

## 6. Frontend UI

### `frontend/src/components/SearchResults.tsx:107-129`

Citations をリンクとして表示：

```tsx
{edge.citations && edge.citations.length > 0 && (
  <div style={styles.citationsContainer}>
    <div style={styles.citationsTitle}>📚 ソース:</div>
    {edge.citations.map((citation, idx) => (
      <div key={idx} style={styles.citation}>
        {citation.source_url ? (
          <a
            href={citation.source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={styles.citationLink}
          >
            🔗 {citation.episode_name}
          </a>
        ) : (
          <span>📄 {citation.episode_name}</span>
        )}
      </div>
    ))}
  </div>
)}
```

## トラブルシューティング

### 「リンクが表示されない」場合

1. **古いデータ**: 新しい ingestion スクリプトで取り込み直してください
   ```bash
   make ingest-github GITHUB_TOKEN=xxx GITHUB_OWNER=xxx GITHUB_REPO=xxx
   make ingest-slack SLACK_TOKEN=xxx WORKSPACE_ID=xxx CHANNEL_ID=xxx
   make ingest-zoom
   ```

2. **検索タイプ**: `search_type="facts"` を使用していることを確認
   - Nodes 検索では citations は含まれません

3. **データ確認**: Neo4j で確認
   ```cypher
   MATCH (e:Episodic)
   WHERE e.source_description CONTAINS 'source_url'
   RETURN e.name, e.source_description
   LIMIT 5
   ```

4. **バックエンドログ確認**:
   ```bash
   docker-compose logs search-bot-backend --tail 100 | grep citations
   ```

## 検証済み

✅ 2025-11-24 時点で全コンポーネントが正しく動作していることを確認済み：

- Ingestion scripts に `source_url` パラメータあり
- Queue service が `source_description` に埋め込み
- Citation service が URL を正しく抽出
- MCP server が citations を返す
- Backend が citations を渡す
- Frontend が citations をリンク表示

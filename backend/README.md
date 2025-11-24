# Graphiti Search Bot Backend

LangChain + Graphitiを使った社内検索BotのバックエンドAPI

## 機能

- **AIチャット**: LangChainを使った対話型検索
- **ナレッジグラフ検索**: Graphitiによる高度な検索
- **Fact編集**: ユーザーによる知識の修正・更新
- **エピソード追加**: 新しい情報の追加

## API エンドポイント

### チャット

```http
POST /api/chat
Content-Type: application/json

{
  "message": "山田さんの役割は？",
  "history": [],
  "include_search_results": true
}
```

### 手動検索

```http
POST /api/search
Content-Type: application/json

{
  "query": "AI機能",
  "limit": 10
}
```

### Fact更新

```http
PUT /api/facts/{edge_uuid}
Content-Type: application/json

{
  "edge_uuid": "uuid-here",
  "new_fact": "修正後のFact",
  "reason": "修正理由"
}
```

### エピソード追加

```http
POST /api/episodes
Content-Type: application/json

{
  "name": "episode_name",
  "content": "エピソード内容",
  "source": "user_input",
  "source_description": "説明"
}
```

## 環境変数

- `NEO4J_URI`: Neo4j接続URI (デフォルト: bolt://neo4j:7687)
- `NEO4J_USER`: Neo4jユーザー名 (デフォルト: neo4j)
- `NEO4J_PASSWORD`: Neo4jパスワード (デフォルト: password123)
- `OPENAI_API_KEY`: OpenAI APIキー (必須)
- `OPENAI_MODEL`: 使用するモデル (デフォルト: gpt-4o-mini)
- `BACKEND_PORT`: サーバーポート (デフォルト: 20001)
- `CORS_ORIGINS`: CORS許可オリジン

## ローカル開発

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn src.main:app --reload --port 20001
```

## Docker

```bash
docker build -t search-bot-backend .
docker run -p 20001:20001 --env-file .env search-bot-backend
```

# ローカルLLM設定ガイド (LM Studio)

企業プロキシのレート制限（429エラー）を回避するために、LM Studioを使用したローカルLLM設定を行うことができます。

## 前提条件

- [LM Studio](https://lmstudio.ai/)がインストールされていること
- 十分なメモリとストレージ容量（モデルサイズに依存）

## LM Studioのセットアップ

### 1. LM Studioのインストールと起動

1. LM Studioを起動
2. 推奨モデルをダウンロード：
   - **LLM**: `openai/gpt-oss-20b` または類似の20B+パラメータモデル
   - **Embedder**: `text-embedding-bge-reranker-v2-m3` または類似のembeddingモデル

### 2. ローカルサーバーの起動

1. LM Studioの「Local Server」タブを開く
2. ダウンロードしたモデルを選択
3. サーバーを起動（デフォルト: `http://localhost:1234`）
4. OpenAI互換APIが有効になっていることを確認

### 3. 接続テスト

```bash
# LLMのテスト
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "max_tokens": 100
  }'

# Embedderのテスト
curl http://localhost:1234/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-bge-reranker-v2-m3",
    "input": "Some text to embed"
  }'
```

## Graphitiの設定

### .envファイルの更新

`.env`ファイルを以下のように設定します：

```bash
# LLM Provider Configuration (using local LM Studio)
LLM__PROVIDER=openai
LLM__MODEL=openai/gpt-oss-20b
LLM__PROVIDERS__OPENAI__API_KEY=dummy-key
LLM__PROVIDERS__OPENAI__API_URL=http://host.docker.internal:1234/v1

# Embedder Provider Configuration (using LM Studio)
EMBEDDER__PROVIDER=openai
EMBEDDER__MODEL=text-embedding-bge-reranker-v2-m3
EMBEDDER__PROVIDERS__OPENAI__API_KEY=dummy-key
EMBEDDER__PROVIDERS__OPENAI__API_URL=http://host.docker.internal:1234/v1
```

**重要なポイント**:
- `host.docker.internal`を使用することで、Dockerコンテナからホストマシンのlocalhost:1234にアクセスできます
- `API_KEY`は`dummy-key`で構いません（ローカルサーバーは認証不要）

### コンテナの再作成

環境変数の変更を反映するため、コンテナを再作成します：

```bash
# 既存のコンテナを停止・削除
docker-compose down

# 新しい設定でコンテナを起動
docker-compose up -d

# ログを確認
docker-compose logs -f graphiti-mcp
```

**注意**: `docker restart`では`.env`の変更が反映されません。必ず`docker-compose down && docker-compose up -d`を実行してください。

## 動作確認

### 1. 環境変数の確認

```bash
docker exec graphiti-search-bot-mcp env | grep -E "LLM__|EMBEDDER__"
```

以下のような出力が表示されるはずです：
```
LLM__PROVIDER=openai
LLM__MODEL=openai/gpt-oss-20b
LLM__PROVIDERS__OPENAI__API_KEY=dummy-key
LLM__PROVIDERS__OPENAI__API_URL=http://host.docker.internal:1234/v1
EMBEDDER__PROVIDER=openai
EMBEDDER__MODEL=text-embedding-bge-reranker-v2-m3
```

### 2. データのインジェスト

テストデータでインジェストを試します：

```bash
make ingest-slack
```

成功すると以下のようなログが表示されます：
```
✓ Successfully ingested 1 messages
✓ Background processing completed successfully
```

### 3. Neo4jでの確認

Neo4jブラウザ（http://localhost:20474）でデータを確認：

```cypher
// Episodicノードの確認
MATCH (n:Episodic) RETURN n LIMIT 10;

// Entityノードの確認
MATCH (n:Entity) RETURN n LIMIT 10;
```

## トラブルシューティング

### エラー: Connection refused (localhost:1234)

**原因**: LM Studioのローカルサーバーが起動していない

**解決方法**:
1. LM Studioを起動
2. 「Local Server」タブでサーバーを起動
3. `http://localhost:1234`でアクセスできることを確認

### エラー: 429 Too Many Requests

**原因**: 企業プロキシの設定が残っている

**解決方法**:
1. `.env`ファイルの`LLM__PROVIDERS__OPENAI__API_URL`を確認
2. `http://host.docker.internal:1234/v1`になっていることを確認
3. `docker-compose down && docker-compose up -d`で再作成

### エンティティ抽出の品質が低い

**原因**: ローカルモデルの性能制限

**解決方法**:
- より大きなモデル（30B+パラメータ）を試す
- プロンプトを調整する（`server/src/services/gpt5_client.py`）
- 企業プロキシでのレート制限が許容範囲内であれば、gpt-4oなどの商用モデルを使用

## パフォーマンス比較

| 設定 | レート制限 | 応答速度 | エンティティ抽出品質 |
|------|----------|---------|-------------------|
| 企業プロキシ (o4-mini) | ⚠️ 3 RPM程度 | ⚡ 高速 | ⭐⭐⭐⭐⭐ 高品質 |
| LM Studio (20B) | ✅ なし | 🐢 中速 | ⭐⭐⭐ 中品質 |
| LM Studio (30B+) | ✅ なし | 🐌 低速 | ⭐⭐⭐⭐ 高品質 |

## 推奨設定

### 開発・テスト環境
- **LM Studio** (openai/gpt-oss-20b) - レート制限なしで快適に開発

### 本番環境
- **企業プロキシ** (gpt-4o) + **レート制限緩和申請** - 高品質なエンティティ抽出

## 参考リンク

- [LM Studio公式サイト](https://lmstudio.ai/)
- [OpenAI API互換性](https://platform.openai.com/docs/api-reference)
- [Graphiti Core Documentation](https://github.com/getzep/graphiti)

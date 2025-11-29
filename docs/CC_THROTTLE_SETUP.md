# cc-throttle レート制限プロキシの設定方法

## 概要

**cc-throttle**は、OpenAI API（および互換API）へのリクエストをレート制限するためのプロキシサーバーです。GraphitiはエピソードをLLMで処理する際、複数のAPIリクエストを並列で送信するため、企業のAPIレート制限（例: 429 Too Many Requests）に抵触しやすい問題があります。

cc-throttleは、リクエストをキューに入れて順次処理することで、レート制限エラーを防ぎます。

## 主な機能

- **レート制限**: 設定したレート（例: 1リクエスト/秒）でAPIリクエストを制御
- **リクエストキュー**: 複数の並列リクエストを自動的にキューイング
- **透過的プロキシ**: OpenAI APIの完全な互換性を保持
- **429エラー対策**: レート制限エラーを根本的に防止

## 必要な環境

- Node.js 18以降 または Bun 1.0以降
- OpenAI API Key（または互換API）

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://ghe.corp.yahoo.co.jp/ytonoyam/cc-throttle-openai
cd cc-throttle
```

### 2. 環境変数の設定

`.env`ファイルを作成します：

```bash
# OpenAI API設定
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# プロキシ設定
PORT=8080

# レート制限設定（ミリ秒）
# 1000 = 1リクエスト/秒
RATE_LIMIT_MS=1000

# Langfuse（オプション）
# LANGFUSE_SECRET_KEY=sk-lf-...
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. 依存関係のインストールと起動

#### Bunを使用する場合（推奨）

```bash
# Bunのインストール（未インストールの場合）
curl -fsSL https://bun.sh/install | bash

# 依存関係のインストール
bun install

# 起動
bun run index.ts
```

#### Node.jsを使用する場合

```bash
npm install
npm start
```

起動すると以下のようなログが表示されます：

```
[2025-11-26T20:15:49.258Z] INFO: Rate-limiting proxy started on http://localhost:8080
[2025-11-26T20:15:49.258Z] INFO: Forwarding to: https://api.openai.com/v1
[2025-11-26T20:15:49.258Z] INFO: Rate limit: 1 request per 1000ms
[2025-11-26T20:15:49.258Z] INFO: Health check: http://localhost:8080/health
```

## Graphitiとの統合

### 環境変数の設定

Graphitiの`.env`ファイルを以下のように設定します：

```bash
# cc-throttleを経由するように設定
LLM__PROVIDERS__OPENAI__API_URL=http://host.docker.internal:8080/v1

# gpt-5などの推論モデルを使用する場合は、トークン数を増やす
LLM__MAX_TOKENS=16000

# cc-throttleのキュー処理に対応するため、タイムアウトを長めに設定
OPENAI_TIMEOUT=600
```

### Docker Composeでの使用

Graphitiのプロジェクトディレクトリで以下を実行：

```bash
# cc-throttleが起動していることを確認
curl http://localhost:8080/health

# Graphitiを起動
docker-compose up -d

# ログを確認して、cc-throttle経由でリクエストが送信されていることを確認
docker-compose logs -f graphiti-mcp
```

## 動作確認

### ヘルスチェック

```bash
curl http://localhost:8080/health
```

成功すると、以下のようなHTMLが返されます（Langfuseの画面）。

### APIリクエストのテスト

```bash
curl -X POST "http://localhost:8080/v1/chat/completions" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

## レート制限の調整

### 企業APIの場合

企業のOpenAI Proxyを使用している場合は、APIのレート制限に応じて調整します：

```bash
# .envファイル
RATE_LIMIT_MS=1000  # 1リクエスト/秒 = 60リクエスト/分
```

### OpenAI公式APIの場合

OpenAI公式APIのレート制限は、プランによって異なります：

- **Free tier**: 3 RPM (Requests Per Minute) → `RATE_LIMIT_MS=20000` (20秒/リクエスト)
- **Pay-as-you-go**:
  - gpt-4o-mini: 500 RPM → `RATE_LIMIT_MS=120` (120ms/リクエスト)
  - gpt-4o: 500 RPM → `RATE_LIMIT_MS=120`
- **Tier 3以上**: より高いレート制限が可能

詳細は[OpenAI Rate Limits](https://platform.openai.com/docs/guides/rate-limits)を参照してください。

## トラブルシューティング

### 429エラーが依然として発生する

**原因**: `RATE_LIMIT_MS`の設定が緩すぎる

**解決策**: レート制限をより厳しく設定します：

```bash
# 現在: 1リクエスト/秒
RATE_LIMIT_MS=1000

# より厳しく: 1リクエスト/2秒
RATE_LIMIT_MS=2000
```

### リクエストがタイムアウトする

**原因**: Graphiti側のタイムアウトが短すぎる

**解決策**: Graphitiの`.env`で`OPENAI_TIMEOUT`を増やします：

```bash
# 現在: 600秒 (10分)
OPENAI_TIMEOUT=600

# より長く: 1200秒 (20分)
OPENAI_TIMEOUT=1200
```

### gpt-5で空のレスポンスが返る

**原因**: gpt-5は推論モデルで、structured output使用時に大量のreasoning_tokensを消費するため、`max_completion_tokens`が足りない

**解決策**: Graphitiの`.env`で`LLM__MAX_TOKENS`を増やします：

```bash
# 推奨: 16000以上
LLM__MAX_TOKENS=16000

# さらに大きく（複雑なスキーマの場合）
LLM__MAX_TOKENS=32000
```

### cc-throttleが起動しない

**原因**: ポート8080が既に使用されている

**解決策**: `.env`でポートを変更します：

```bash
PORT=8081
```

そして、Graphitiの`.env`も更新します：

```bash
LLM__PROVIDERS__OPENAI__API_URL=http://host.docker.internal:8081/v1
```

### Bunが見つからない

**原因**: Bunがインストールされていない、またはPATHが通っていない

**解決策**: Bunをインストールしてパスを通します：

```bash
# Bunのインストール
curl -fsSL https://bun.sh/install | bash

# シェルを再起動してPATHを反映
exec $SHELL

# または、フルパスで実行
~/.bun/bin/bun run index.ts
```

## モニタリング

### リクエストのログ確認

cc-throttleは、すべてのリクエストをログに記録します：

```
[2025-11-26T20:16:00.084Z] INFO: Queued: GET /v1/models - Queue size: 1
[2025-11-26T20:16:01.319Z] INFO: Processed: GET /v1/models - Status: 200
[2025-11-26T20:22:49.625Z] INFO: Queued: POST /v1/chat/completions - Queue size: 1
[2025-11-26T20:23:28.818Z] INFO: Processed: POST /v1/chat/completions - Status: 200
```

### キューサイズの確認

大量のリクエストが溜まっている場合、キューサイズが大きくなります：

```
[2025-11-26T20:34:18.291Z] INFO: Queued: POST /v1/chat/completions - Queue size: 19
```

この場合、処理完了までに時間がかかるため、`OPENAI_TIMEOUT`を増やすことを推奨します。

## ベストプラクティス

1. **レート制限は保守的に設定**: APIプロバイダーのレート制限より少し余裕を持たせる
2. **タイムアウトは長めに設定**: キューが溜まった場合でも処理できるように
3. **ログをモニタリング**: キューサイズや429エラーの発生を監視
4. **推論モデルはトークン数を多めに**: gpt-5などはreasoning_tokensを大量に消費する

## 関連ドキュメント

- [cc-throttle GitHub Repository](https://github.com/linecorp/cc-throttle)
- [OpenAI Rate Limits](https://platform.openai.com/docs/guides/rate-limits)
- [Graphiti Setup Guide](../SETUP.md)
- [Local LLM Setup](./LOCAL_LLM_SETUP.md)

## FAQ

### Q: cc-throttleなしでGraphitiを使用できますか？

A: 可能ですが、並列リクエストが多いため429エラーが発生しやすくなります。企業のAPIや無料プランを使用している場合は、cc-throttleの使用を強く推奨します。

### Q: cc-throttleはDocker化できますか？

A: はい。Dockerfileを作成してコンテナ化することも可能です。ただし、`host.docker.internal`を使用してGraphitiからアクセスする場合は、ホスト上で直接起動する方が簡単です。

### Q: 複数のGraphitiインスタンスで1つのcc-throttleを共有できますか？

A: はい。cc-throttleは複数のクライアントからのリクエストを処理できます。ただし、全体のレート制限に注意してください。

### Q: Langfuseとの連携は必須ですか？

A: いいえ、オプションです。Langfuseを使用しない場合は、`.env`からLangfuse関連の環境変数を削除してください。

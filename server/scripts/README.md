# Slackデータ翻訳スクリプト

このディレクトリには、Graphitiへのインポート前にSlackデータを前処理するスクリプトが含まれています。

## translate_slack_data.py

`slack_data/threads_ordered.csv`内の日本語コンテンツを英語に翻訳し、`threads_ordered_en.csv`として保存します。

### 特徴

- **非破壊的**: 元の日本語CSVファイルを保持
- **完全翻訳**: システムメッセージを含む全ての日本語コンテンツを英語に翻訳
- **バッチ処理**: async/awaitを使用して複数メッセージを効率的に翻訳
- **進捗表示**: プログレスバーでリアルタイム進捗を表示
- **エラーハンドリング**: 失敗時にリトライし、エラー発生時も継続
- **自動検出**: データローダーは英語CSVが利用可能な場合、自動的に使用

### 使い方

```bash
# graphiti-mcpコンテナをビルドして起動
docker-compose up -d graphiti-mcp

# コンテナ内で翻訳スクリプトを実行
docker-compose exec graphiti-mcp python scripts/translate_slack_data.py

# 英語CSVが作成されたことを確認
ls -lh graphiti_mcp/slack_data/threads_ordered*.csv
```

### 設定

スクリプトは`graphiti_mcp/.env`からOpenAI API認証情報を使用します：

```env
OPENAI_API_KEY=your_api_key_here
```

スクリプト内で翻訳パラメータをカスタマイズできます：
- `model`: 使用するOpenAIモデル（デフォルト: `gpt-4o-mini`）
- `batch_size`: 1回のAPI呼び出しあたりのメッセージ数（デフォルト: 10）
- `max_concurrent`: 同時実行するAPIリクエスト数（デフォルト: 10）

### 出力ファイル

- **元ファイル**: `threads_ordered.csv`（保持、日本語）
- **翻訳ファイル**: `threads_ordered_en.csv`（自動作成、英語）

### データローダーの動作

データローディングスクリプト（[load_slack_data.py](../src/load_slack_data.py)、[load_slack_data_enhanced.py](../src/load_slack_data_enhanced.py)）は自動的に：
1. `threads_ordered_en.csv`が存在するか確認
2. 存在する場合は英語版を使用
3. 存在しない場合は元の`threads_ordered.csv`にフォールバック

つまり、**英語CSVが存在する場合、新しいデータ入力は自動的に翻訳されます**。

### コスト見積もり

`gpt-4o-mini`を使用した約200-300メッセージの場合：
- 約$0.02-0.05 USD/実行
- 翻訳時間は約20-30秒

### 実行例

```bash
$ docker-compose exec graphiti-mcp python scripts/translate_slack_data.py

Loading CSV from: /app/slack_data/threads_ordered.csv
Loaded 225 rows

Found 193 messages to translate
Translating batches: 100%|██████████| 20/20 [00:28<00:00,  1.44s/it]

Translation complete!
Original file preserved: /app/slack_data/threads_ordered.csv
Translated file saved: /app/slack_data/threads_ordered_en.csv
```

### ワークフロー

```
┌─────────────────────────┐
│ threads_ordered.csv     │  ← 元の日本語データ
│ (日本語)                │
└───────────┬─────────────┘
            │
            │ python scripts/translate_slack_data.py
            │
            ▼
┌─────────────────────────┐
│ threads_ordered_en.csv  │  ← 翻訳された英語データ
│ (英語)                  │
└───────────┬─────────────┘
            │
            │ データローダーが自動検出して使用
            │
            ▼
┌─────────────────────────┐
│ Graphiti Knowledge      │
│ Graph (英語)            │
└─────────────────────────┘
```

### データの検索

翻訳されたデータがGraphitiに投入された後、以下のコマンドで検索できます：

```bash
# GraphRAGについて検索
docker-compose exec graphiti-mcp python src/query.py --query "about GraphRAG"

# 特定のトピックについて検索
docker-compose exec graphiti-mcp python src/query.py --query "AI agent implementation"

# ユーザーの発言を検索
docker-compose exec graphiti-mcp python src/query.py --query "What did Takuto Nariura say"
```

**重要**: データは英語に翻訳されているため、検索クエリも英語で記述してください。

検索結果はJSON形式で返されます。`--max_facts`オプションで結果数を変更できます（デフォルト: 5）。

詳細は[query.py](../src/query.py)を参照してください。

### トラブルシューティング

**ModuleNotFoundError**: Dockerコンテナ内で実行していることを確認してください。

**API Key Error**: `graphiti_mcp/.env`に`OPENAI_API_KEY`が設定されているか確認してください。

**Rate Limit**: OpenAIのレート制限に達した場合は、スクリプト内の`max_concurrent`を減らしてください。

**File not found**: `slack_data/`ディレクトリに`threads_ordered.csv`が存在することを確認してください。

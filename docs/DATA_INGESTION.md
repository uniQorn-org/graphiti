# Graphiti データ取り込みガイド

> **Version**: 1.0
> **Last Updated**: 2025-11-29

このドキュメントは、外部データソースからGraphitiナレッジグラフへデータを取り込む方法を説明します。

## 目次

- [概要](#概要)
- [Ingestion Scripts の使い方](#ingestion-scripts-の使い方)
- [BaseIngester クラス](#baseingester-クラス)
- [既存データソース](#既存データソース)
- [カスタムデータソースの追加](#カスタムデータソースの追加)
- [翻訳機能](#翻訳機能)
- [source_url の指定](#source_url-の指定)
- [バッチ処理のベストプラクティス](#バッチ処理のベストプラクティス)
- [トラブルシューティング](#トラブルシューティング)

---

## 概要

Graphitiへのデータ取り込みは、**Ingestion Scripts** を通じて行います。これらのスクリプトは：

- 外部データソース（GitHub, Slack, Zoom等）からデータを取得
- データをEpisode形式に変換
- MCP Client経由でGraphiti MCPサーバーに送信
- メタデータ（source_url等）を適切に埋め込み

### データ取り込みフロー

```
外部データソース
    ↓ (1) API/ファイルアクセス
Ingestion Script
    ↓ (2) fetch_data()
生データ (JSON/Dict)
    ↓ (3) build_episode()
Episode形式
    ↓ (4) MCPClient.add_episode()
    ↓     HTTP POST to MCP Server
Graphiti MCP Server
    ↓ (5) QueueService → graphiti-core
    ↓ (6) エンティティ抽出 (LLM)
Neo4j Database
```

---

## Ingestion Scripts の使い方

### ディレクトリ構造

```
server/src/ingestion/
├── __init__.py
├── base.py              # BaseIngester基底クラス
├── mcp_client.py        # MCPクライアント
├── github.py            # GitHub Issues取り込み
├── slack.py             # Slackメッセージ取り込み
├── zoom.py              # Zoom文字起こし取り込み
└── utils.py             # ユーティリティ関数
```

### 基本的な実行方法

#### 1. GitHub Issues の取り込み

```bash
# 環境変数設定
export GITHUB_TOKEN="your_github_token"
export GRAPHITI_MCP_URL="http://localhost:30547"

# Pythonスクリプト実行
cd server/src/ingestion
python -m github
```

または、Dockerコンテナ内で実行:

```bash
# docker-compose経由
make ingest-github

# または直接実行
docker exec -it graphiti-search-bot-mcp \
  python -m ingestion.github
```

#### 2. Slack Messages の取り込み

```bash
# 環境変数設定
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_CHANNEL_ID="C123456"
export GRAPHITI_MCP_URL="http://localhost:30547"

# 実行
python -m ingestion.slack
```

#### 3. Zoom Transcripts の取り込み

```bash
# MinIOバケットからファイルを読み込み
export MINIO_ENDPOINT="localhost:20734"
export MINIO_ACCESS_KEY="minio"
export MINIO_SECRET_KEY="miniosecret"
export GRAPHITI_MCP_URL="http://localhost:30547"

# 実行（CLIスクリプト使用）
python server/src/scripts/ingest_zoom.py \
  --data-dir /app/data/zoom \
  --minio-endpoint localhost:20734 \
  --mcp-url http://localhost:8001/mcp/

# または、Dockerコンテナ内で実行
docker-compose exec graphiti-mcp python scripts/ingest_zoom.py --data-dir /app/data/zoom
```

**Note**: Zoom ingesterは設定クラス（`ZoomIngestionConfig`）を使用しています。詳細は「設定クラスの使用」セクションを参照してください。

---

## BaseIngester クラス

すべてのIngesterは `BaseIngester` を継承します。

### クラス定義

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pathlib import Path

class BaseIngester(ABC):
    """すべてのデータ取り込みの基底クラス"""

    def __init__(
        self,
        mcp_url: str = "http://localhost:8001/mcp/",
        translate: bool = True,
        save_to_disk: bool = True,
        data_dir: Path | None = None,
    ):
        """
        Args:
            mcp_url: MCPサーバーのURL
            translate: 英語に翻訳するか
            save_to_disk: 生データをディスクに保存するか
            data_dir: データ保存ディレクトリ（デフォルト: /app/data/{source_type}）
        """
        self.mcp_url = mcp_url
        self.translate = translate
        self.save_to_disk = save_to_disk
        self.data_dir = data_dir
        self.mcp_client = MCPClient(mcp_url)

        # 翻訳機能の初期化
        if translate:
            from translator import translate_with_limit
            self.translator = translate_with_limit

    @abstractmethod
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """データソースからデータを取得

        Returns:
            取り込むデータアイテムのリスト

        Raises:
            Exception: データ取得に失敗した場合
        """
        pass

    @abstractmethod
    def build_episode(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """生データをEpisode形式に変換

        Args:
            data: 生データアイテム

        Returns:
            Episode dict with keys:
            - name: エピソード名
            - episode_body: エピソード本文
            - source: ソースタイプ ("text", "json", "message")
            - source_description: ソースの説明
            - source_url: ソースURL（重要！）
        """
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """ソースタイプ識別子を取得

        Returns:
            ソースタイプ文字列（例: "github", "slack", "zoom"）
        """
        pass

    async def ingest(self, clear_existing: bool = False) -> Dict[str, Any]:
        """取り込みパイプラインを実行

        Args:
            clear_existing: 既存グラフデータを削除するか

        Returns:
            取り込み結果のサマリー
        """
        print(f"🚀 Starting {self.get_source_type()} ingestion...")

        # 1. データ取得
        print("📡 Fetching data...")
        data = await self.fetch_data()
        print(f"✓ Found {len(data)} items")

        # 2. ディスクに保存（オプション）
        if self.save_to_disk:
            filepath = self.save_data(data)
            print(f"✓ Saved raw data to: {filepath}")

        # 3. MCPクライアント経由で投入
        async with self.mcp_client.connect() as session:
            if clear_existing:
                print("🗑️  Clearing existing graph data...")
                await self.mcp_client.clear_graph(session)

            success_count = 0
            error_count = 0

            for item in tqdm(data, desc=f"Ingesting {self.get_source_type()} items"):
                try:
                    episode = self.build_episode(item)
                    await self.mcp_client.add_episode(session, **episode)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"✗ Error processing item: {e}")

        # サマリー表示
        print("\n" + "=" * 60)
        print("📊 Ingestion Summary")
        print("=" * 60)
        print(f"Source: {self.get_source_type()}")
        print(f"Total items: {len(data)}")
        print(f"✓ Success: {success_count}")
        print(f"✗ Errors: {error_count}")
        print("=" * 60)

        return {
            "source_type": self.get_source_type(),
            "total": len(data),
            "success": success_count,
            "errors": error_count,
        }
```

---

## 既存データソース

### 1. GitHub Issues Ingester

**ファイル**: [server/src/ingestion/github.py](../server/src/ingestion/github.py)

#### 機能
- GitHub APIからIssuesとコメントを取得
- Issueの本文とコメントを結合
- メタデータ（ラベル、マイルストーン等）を保持

#### 設定

```bash
# 環境変数
export GITHUB_TOKEN="ghp_xxxxx"
export GITHUB_REPO="owner/repo"
export GITHUB_STATE="all"  # all, open, closed
```

#### 実装例

```python
class GitHubIngester(BaseIngester):
    def get_source_type(self) -> str:
        return "github"

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """GitHub APIからIssuesを取得"""
        github = Github(self.token)
        repo = github.get_repo(self.repo_name)
        issues = repo.get_issues(state=self.state)

        data = []
        for issue in issues:
            # Issueとコメントを取得
            comments = [c.body for c in issue.get_comments()]
            data.append({
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "comments": comments,
                "html_url": issue.html_url,
                "created_at": issue.created_at,
                "labels": [l.name for l in issue.labels],
            })
        return data

    def build_episode(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """IssueをEpisode形式に変換"""
        # 本文とコメントを結合
        full_text = f"# {issue['title']}\n\n{issue['body']}"
        if issue['comments']:
            full_text += "\n\n## Comments\n\n"
            full_text += "\n\n---\n\n".join(issue['comments'])

        # 翻訳（オプション）
        if self.translate:
            full_text = self.translate_text(full_text)

        return {
            "name": f"github_issue_{issue['number']}",
            "episode_body": full_text,
            "source": "text",
            "source_description": f"GitHub Issue #{issue['number']}: {issue['title']}",
            "source_url": issue['html_url'],  # 重要: source_url指定
            "reference_time": issue['created_at'],
        }
```

### 2. Slack Messages Ingester

**ファイル**: [server/src/ingestion/slack.py](../server/src/ingestion/slack.py)

#### 機能
- Slack APIからチャンネルメッセージを取得
- スレッド返信を含む
- ユーザー情報の解決

#### 設定

```bash
# 環境変数
export SLACK_BOT_TOKEN="xoxb-xxxxx"
export SLACK_CHANNEL_ID="C123456"
export SLACK_DAYS_BACK="30"  # 取得日数
```

#### 実装例

```python
class SlackIngester(BaseIngester):
    def get_source_type(self) -> str:
        return "slack"

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Slack APIからメッセージを取得"""
        client = WebClient(token=self.bot_token)

        # 期間指定
        oldest = (datetime.now() - timedelta(days=self.days_back)).timestamp()

        # メッセージ取得
        result = client.conversations_history(
            channel=self.channel_id,
            oldest=oldest,
            limit=1000,
        )

        messages = []
        for msg in result["messages"]:
            # スレッド返信を取得
            if msg.get("thread_ts"):
                replies = client.conversations_replies(
                    channel=self.channel_id,
                    ts=msg["thread_ts"]
                )
                msg["replies"] = replies["messages"][1:]  # 最初は元メッセージ

            messages.append(msg)

        return messages

    def build_episode(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """SlackメッセージをEpisode形式に変換"""
        # ユーザー名解決
        user = self.get_user_name(message["user"])

        # メッセージ本文
        text = f"{user}: {message['text']}"

        # スレッド返信を追加
        if message.get("replies"):
            text += "\n\nThread:"
            for reply in message["replies"]:
                reply_user = self.get_user_name(reply["user"])
                text += f"\n  {reply_user}: {reply['text']}"

        # 翻訳
        if self.translate:
            text = self.translate_text(text)

        # Slackパーマリンク生成
        ts = message["ts"].replace(".", "")
        permalink = f"https://slack.com/archives/{self.channel_id}/p{ts}"

        return {
            "name": f"slack_msg_{message['ts']}",
            "episode_body": text,
            "source": "message",
            "source_description": f"Slack message from {user}",
            "source_url": permalink,
            "reference_time": datetime.fromtimestamp(float(message["ts"])),
        }
```

### 3. Zoom Transcripts Ingester

**ファイル**: [server/src/ingestion/zoom.py](../server/src/ingestion/zoom.py)

#### 機能
- MinIOバケットからZoom文字起こしファイルを取得
- VTT/SRT形式をパース
- 話者情報を保持

#### 設定

ZoomIngesterは **設定クラスパターン** を使用します（Phase 12で導入）：

```python
from ingestion.config import ZoomIngestionConfig

# 設定オブジェクトを作成
zoom_config = ZoomIngestionConfig(
    data_dir="/app/data/zoom",
    minio_endpoint="localhost:20734",
    minio_access_key="minio",
    minio_secret_key="miniosecret",
    bucket_name="zoom-transcripts",
    translate_to_english=True,  # 自動翻訳を有効化
)

# Ingesterを初期化（1パラメータのみ！）
ingester = ZoomIngester(
    config=zoom_config,
    mcp_url="http://localhost:8001/mcp/",
)
```

**利点:**
- パラメータ数を7個から1個に削減（86%削減）
- Pydanticによる型安全な検証
- IDE自動補完のサポート向上
- 設定の拡張が容易

#### 実装例

```python
class ZoomIngester(BaseIngester):
    def __init__(self, config: ZoomIngestionConfig, **kwargs):
        """Zoom ingesterの初期化

        Args:
            config: Zoom ingestion configuration object
            **kwargs: BaseIngester用の追加引数
        """
        super().__init__(**kwargs)
        self.vtt_dir = Path(config.data_dir)
        self.minio_endpoint = config.minio_endpoint
        # ... 設定から値を取得

    def get_source_type(self) -> str:
        return "zoom"

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """MinIOからZoom文字起こしを取得"""
        from minio import Minio

        client = Minio(
            self.minio_endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=False,
        )

        transcripts = []
        objects = client.list_objects(self.bucket, recursive=True)

        for obj in objects:
            if obj.object_name.endswith(".vtt"):
                # VTTファイルをダウンロード
                data = client.get_object(self.bucket, obj.object_name)
                content = data.read().decode("utf-8")

                transcripts.append({
                    "filename": obj.object_name,
                    "content": content,
                    "last_modified": obj.last_modified,
                })

        return transcripts

    def build_episode(self, transcript: Dict[str, Any]) -> Dict[str, Any]:
        """Zoom文字起こしをEpisode形式に変換"""
        # VTTパース
        lines = self.parse_vtt(transcript["content"])

        # テキスト結合
        full_text = "\n".join([f"{line['speaker']}: {line['text']}" for line in lines])

        # 翻訳
        if self.translate:
            full_text = self.translate_text(full_text, max_chars=50000)

        # ファイル名からミーティングIDを抽出
        meeting_id = self.extract_meeting_id(transcript["filename"])

        return {
            "name": f"zoom_meeting_{meeting_id}",
            "episode_body": full_text,
            "source": "text",
            "source_description": f"Zoom meeting transcript: {transcript['filename']}",
            "source_url": f"https://minio.example.com/{self.bucket}/{transcript['filename']}",
            "reference_time": transcript["last_modified"],
        }

    def parse_vtt(self, content: str) -> List[Dict[str, Any]]:
        """VTT形式をパース"""
        lines = []
        for block in content.split("\n\n"):
            if "-->" in block:
                parts = block.split("\n")
                speaker = parts[2].split(":")[0] if len(parts) > 2 else "Unknown"
                text = " ".join(parts[2:])
                lines.append({"speaker": speaker, "text": text})
        return lines
```

---

## カスタムデータソースの追加

### ステップ1: Ingesterクラスを作成

```python
# server/src/ingestion/custom_source.py

from typing import Any, Dict, List
from .base import BaseIngester

class CustomSourceIngester(BaseIngester):
    """カスタムデータソースのIngester"""

    def __init__(
        self,
        mcp_url: str = "http://localhost:8001/mcp/",
        custom_api_key: str = None,
        **kwargs
    ):
        super().__init__(mcp_url, **kwargs)
        self.api_key = custom_api_key

    def get_source_type(self) -> str:
        """ソースタイプを返す"""
        return "custom_source"

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """データソースからデータを取得

        ここでAPI呼び出し、ファイル読み込み等を実装
        """
        # 例: REST API呼び出し
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.example.com/items",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            return response.json()["items"]

    def build_episode(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """データをEpisode形式に変換

        重要: source_urlを必ず指定すること！
        """
        return {
            "name": f"custom_{data['id']}",
            "episode_body": data['content'],
            "source": "text",  # or "json", "message"
            "source_description": f"Custom source item {data['id']}",
            "source_url": data['url'],  # 必須！
            "reference_time": data.get('created_at'),  # オプション
        }
```

### ステップ2: 実行スクリプトを作成

```python
# server/src/ingestion/run_custom.py

import asyncio
from custom_source import CustomSourceIngester

async def main():
    ingester = CustomSourceIngester(
        mcp_url="http://localhost:30547/mcp/",
        custom_api_key="your_api_key",
        translate=True,
        save_to_disk=True,
    )

    # 取り込み実行
    result = await ingester.ingest(clear_existing=False)
    print(f"Ingestion completed: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### ステップ3: 実行

```bash
cd server/src/ingestion
python run_custom.py
```

---

## 翻訳機能

### 概要

`translate=True` を指定すると、取り込み時にコンテンツを英語に翻訳します。

### 翻訳の仕組み

```python
# translator.py

def translate_with_limit(text: str, max_chars: int = 10000) -> str:
    """テキストを英語に翻訳（文字数制限あり）

    Args:
        text: 翻訳するテキスト
        max_chars: 最大文字数（超過分は切り捨て）

    Returns:
        翻訳されたテキスト
    """
    # 文字数制限
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    # OpenAI API呼び出し
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Translate the following text to English."},
            {"role": "user", "content": text}
        ]
    )

    return response.choices[0].message.content
```

### 使い方

```python
class MyIngester(BaseIngester):
    def build_episode(self, data: Dict[str, Any]) -> Dict[str, Any]:
        text = data['content']

        # 翻訳を適用
        if self.translate:
            text = self.translate_text(text, max_chars=20000)

        return {
            "name": f"item_{data['id']}",
            "episode_body": text,
            # ...
        }
```

### 注意点

- 翻訳にはOpenAI APIを使用（コストに注意）
- 大量のテキストは分割して翻訳
- `max_chars` パラメータで制限

---

## source_url の指定

### 重要性

`source_url` は情報の出典を示す最も重要なメタデータです。必ず指定してください。

### 指定方法

```python
def build_episode(self, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": "episode_name",
        "episode_body": "content",
        "source": "text",
        "source_description": "Description",
        "source_url": "https://example.com/source/123",  # ここ！
    }
```

### 埋め込まれる形式

Graphiti内部では以下のように埋め込まれます：

```python
# queue_service.pyでの処理
source_description = "Description"
source_url = "https://example.com/source/123"

final_source_description = f"{source_description}, source_url: {source_url}"
# => "Description, source_url: https://example.com/source/123"
```

### 抽出

Citation情報取得時に正規表現で抽出されます：

```python
# citation_service.py
def extract_source_url(source_description: str) -> str | None:
    match = re.search(r'source_url:\s*(https?://[^\s,]+)', source_description)
    if match:
        return match.group(1)
    return None
```

### パーマリンクの生成例

#### Slack

```python
# タイムスタンプからパーマリンク生成
ts = message["ts"].replace(".", "")
channel_id = "C123456"
source_url = f"https://slack.com/archives/{channel_id}/p{ts}"
```

#### GitHub

```python
# IssueのHTMLURL
source_url = issue["html_url"]
# => "https://github.com/owner/repo/issues/123"
```

#### MinIO

```python
# MinIOオブジェクトURL
bucket = "zoom-transcripts"
filename = "meeting_123.vtt"
source_url = f"https://minio.example.com/{bucket}/{filename}"
```

---

## バッチ処理のベストプラクティス

### 1. 段階的な取り込み

大量データは段階的に取り込みます：

```python
async def ingest_in_batches(self, batch_size: int = 100):
    """バッチ単位で取り込み"""
    all_data = await self.fetch_data()

    for i in range(0, len(all_data), batch_size):
        batch = all_data[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}...")

        async with self.mcp_client.connect() as session:
            for item in batch:
                episode = self.build_episode(item)
                await self.mcp_client.add_episode(session, **episode)

        # バッチ間で待機（レート制限対策）
        await asyncio.sleep(60)
```

### 2. エラーハンドリング

```python
async def ingest(self, clear_existing: bool = False):
    """エラーハンドリング付き取り込み"""
    errors = []

    for item in data:
        try:
            episode = self.build_episode(item)
            await self.mcp_client.add_episode(session, **episode)
        except Exception as e:
            errors.append({
                "item": item,
                "error": str(e)
            })
            # エラーログ保存
            self.save_error_log(errors)

    # エラーサマリー表示
    if errors:
        print(f"\n⚠️  {len(errors)} items failed")
        for err in errors[:5]:  # 最初の5件を表示
            print(f"  - {err['item']['name']}: {err['error']}")
```

### 3. プログレスバー

```python
from tqdm import tqdm

async def ingest(self):
    """プログレスバー付き取り込み"""
    data = await self.fetch_data()

    with tqdm(total=len(data), desc="Ingesting") as pbar:
        for item in data:
            episode = self.build_episode(item)
            await self.mcp_client.add_episode(session, **episode)
            pbar.update(1)
```

### 4. ディスク保存

生データを保存しておくと再取り込みが簡単：

```python
def save_data(self, data: List[Dict[str, Any]]) -> Path:
    """生データをJSONで保存"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{self.get_source_type()}_data_{timestamp}.json"
    filepath = self.data_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "source_type": self.get_source_type(),
            "fetched_at": datetime.now().isoformat(),
            "item_count": len(data),
            "data": data,
        }, f, ensure_ascii=False, indent=2)

    return filepath
```

---

## トラブルシューティング

### 問題1: レート制限エラー（429）

**症状**: `Rate limit exceeded` エラー

**解決策**:
1. `SEMAPHORE_LIMIT` を下げる（環境変数）
2. `EPISODE_PROCESSING_DELAY` を増やす
3. バッチ間に待機時間を入れる

```python
# .env
SEMAPHORE_LIMIT=5
EPISODE_PROCESSING_DELAY=30
```

### 問題2: 翻訳が遅い

**症状**: 取り込みに時間がかかりすぎる

**解決策**:
1. `translate=False` にして翻訳をスキップ
2. `max_chars` を減らす
3. 並列翻訳を実装

```python
# 翻訳なし
ingester = MyIngester(translate=False)

# 文字数制限
self.translate_text(text, max_chars=5000)
```

### 問題3: source_url が表示されない

**症状**: Citation に source_url が含まれない

**解決策**:
1. `build_episode()` で `source_url` を指定しているか確認
2. URLの形式が正しいか確認（http/https）
3. 正規表現パターンにマッチするか確認

```python
# デバッグ
print(f"source_url: {episode['source_url']}")
print(f"source_description: {final_source_description}")

# 抽出テスト
from services.citation_service import extract_source_url
url = extract_source_url(final_source_description)
print(f"Extracted URL: {url}")
```

### 問題4: メモリ不足

**症状**: 大量データ取り込み時にメモリエラー

**解決策**:
1. バッチ処理に切り替え
2. `save_to_disk=False` にする
3. ストリーミング処理を実装

```python
# ストリーミング処理
async def fetch_data_stream(self):
    """データをストリームで取得"""
    for page in range(1, max_pages):
        items = await self.fetch_page(page)
        for item in items:
            yield item

async def ingest(self):
    """ストリーミング取り込み"""
    async for item in self.fetch_data_stream():
        episode = self.build_episode(item)
        await self.mcp_client.add_episode(session, **episode)
```

---

## 参考資料

- [メタデータ仕様書](./METADATA_SPECIFICATION.md)
- [アーキテクチャドキュメント](./ARCHITECTURE.md)
- [BaseIngester実装](../server/src/ingestion/base.py)
- [GitHub Ingester実装](../server/src/ingestion/github.py)
- [Slack Ingester実装](../server/src/ingestion/slack.py)
- [Zoom Ingester実装](../server/src/ingestion/zoom.py)

---

## バージョン履歴

- **1.1** (2025-11-29): Phase 12リファクタリング反映
  - ZoomIngesterの設定クラスパターン導入
  - `ZoomIngestionConfig`の使用方法を追加
  - パラメータ削減（7個→1個）の説明

- **1.0** (2025-11-29): 初版作成
  - BaseIngesterの使い方
  - 既存データソースの説明
  - カスタムデータソースの追加方法
  - 翻訳機能とsource_url指定
  - バッチ処理のベストプラクティス
  - トラブルシューティング

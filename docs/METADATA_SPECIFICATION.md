# Graphiti メタデータ仕様書

> **Version**: 1.0
> **Last Updated**: 2025-11-29

このドキュメントは、Graphitiシステムにおけるメタデータの完全な仕様を説明します。

## 目次

- [概要](#概要)
- [アーキテクチャの前提知識](#アーキテクチャの前提知識)
- [Episode (エピソード) メタデータ](#episode-エピソード-メタデータ)
- [Node (エンティティ) メタデータ](#node-エンティティ-メタデータ)
- [Edge (Fact/関係) メタデータ](#edge-fact関係-メタデータ)
- [Citation (引用情報) メタデータ](#citation-引用情報-メタデータ)
- [Entity Types (エンティティタイプ定義)](#entity-types-エンティティタイプ定義)
- [API リクエスト/レスポンス型](#api-リクエストレスポンス型)
- [実装上の重要な設計パターン](#実装上の重要な設計パターン)

---

## 概要

Graphitiは時間情報付きナレッジグラフを構築するシステムです。データは以下の3つの主要な要素で構成されます：

1. **Episode (エピソード)**: 情報の入力単位
2. **Node (ノード)**: 抽出されたエンティティ
3. **Edge (エッジ)**: エンティティ間の関係（Fact）

各要素は豊富なメタデータを持ち、時間情報、出典情報、更新履歴などを追跡します。

---

## アーキテクチャの前提知識

Graphitiシステムは3層に分離されています：

```
┌─────────────────────────────────────┐
│      Graphiti MCP Server            │  ← Neo4jに直接接続
│      (Port 30547)                   │
└─────────────────────────────────────┘
                ↑ HTTP/MCP
┌─────────────────────────────────────┐
│      Chat Backend                   │  ← MCPクライアント経由
│      (Port 20001)                   │
└─────────────────────────────────────┘
                ↑ HTTP
┌─────────────────────────────────────┐
│      Data Ingestion Scripts         │  ← MCPクライアント経由
└─────────────────────────────────────┘
```

詳細は [ARCHITECTURE.md](./ARCHITECTURE.md) を参照してください。

---

## Episode (エピソード) メタデータ

Episodeは、Graphitiに投入される情報の単位です。テキスト、JSON、メッセージなど様々な形式をサポートします。

### フィールド一覧

| フィールド | 型 | 必須 | 説明 |
|-----------|----|----|------|
| `uuid` | string | ✓ | エピソードの一意識別子 |
| `name` | string | ✓ | エピソード名（例: "slack_message_123", "github_issue_456"） |
| `content` | string | ✓ | エピソードの本文内容 |
| `source` | EpisodeType | ✓ | ソースタイプ（`text`, `json`, `message`） |
| `source_description` | string | ✓ | ソースの説明文（**`source_url`が埋め込まれる**） |
| `source_url` | string | - | ソースURL（オプション、`source_description`に埋め込まれる） |
| `group_id` | string | ✓ | グループID（名前空間） |
| `created_at` | datetime | ✓ | エピソードが作成された時刻 |
| `reference_time` | datetime | - | エピソードが発生した時刻（指定可能、デフォルトは現在時刻） |

### source_url の重要な仕様

**`source_url` は独立したフィールドとして保存されません。**
代わりに、`source_description` フィールドに以下の形式で埋め込まれます：

```
"{source_description}, source_url: {url}"
```

#### 実装例

**埋め込み処理** ([queue_service.py:149-155](../server/src/services/queue_service.py#L149-L155)):
```python
# source_urlをsource_descriptionに埋め込み
final_source_description = source_description
if source_url:
    if source_description:
        final_source_description = f"{source_description}, source_url: {source_url}"
    else:
        final_source_description = f"source_url: {source_url}"
```

**抽出処理** ([citation_service.py:14-30](../server/src/services/citation_service.py#L14-L30)):
```python
def extract_source_url(source_description: str) -> str | None:
    """Extract source_url from source_description string."""
    if not source_description:
        return None

    # Match "source_url: " followed by URL (http/https)
    match = re.search(r'source_url:\s*(https?://[^\s,]+)', source_description)
    if match:
        return match.group(1)
    return None
```

### reference_time の使い方

`reference_time`は、エピソードが**実際に発生した時刻**を表します。例えば：

- Slackメッセージの送信時刻
- GitHubイシューの作成時刻
- Zoom会議の開催時刻

指定しない場合は、現在時刻が使用されます。

```python
# reference_timeを指定する例
await graphiti.add_episode(
    name="slack_msg_123",
    episode_body="プロジェクトの進捗報告",
    source=EpisodeType.message,
    source_description="Slackメッセージ",
    source_url="https://slack.com/archives/C123/p456",
    reference_time=datetime(2025, 11, 25, 14, 30, 0, tzinfo=timezone.utc)
)
```

### Episode データモデル

```python
class EpisodeCreateRequest(BaseModel):
    """エピソード作成リクエスト"""
    name: str
    content: str
    group_id: Optional[str] = None
    source: Literal["text", "json", "message"] = "text"
    source_description: Optional[str] = ""
    source_url: Optional[str] = None  # APIで受け取り、内部で埋め込み
    uuid: Optional[str] = None
```

---

## Node (エンティティ) メタデータ

Nodeは、Episodeから抽出されたエンティティを表します。

### フィールド一覧

| フィールド | 型 | 必須 | 説明 |
|-----------|----|----|------|
| `uuid` | string | ✓ | ノードの一意識別子 |
| `name` | string | ✓ | エンティティ名（例: "山田太郎", "プロジェクトA"） |
| `summary` | string | - | エンティティの要約説明 |
| `created_at` | datetime | ✓ | ノードの作成日時 |
| `labels` | List[str] | ✓ | エンティティタイプのラベル（例: `["Organization"]`） |
| `attributes` | Dict[str, Any] | ✓ | カスタム属性（embeddings除外） |
| `group_id` | string | ✓ | グループID |

### Node データモデル

```python
class EntityNode(BaseModel):
    """エンティティノード"""
    uuid: str
    name: str
    summary: Optional[str] = None
    created_at: datetime
    labels: List[str] = []
    attributes: Dict[str, Any] = {}
```

### 注意事項

- `attributes` からは `embedding` キーが除外されます（検索結果に含めない）
- `labels` はエンティティタイプを示します（後述の[Entity Types](#entity-types-エンティティタイプ定義)参照）

---

## Edge (Fact/関係) メタデータ

Edgeは、2つのNode間の関係（Fact）を表します。Graphitiの中核的な要素です。

### フィールド一覧

| フィールド | 型 | 必須 | 説明 |
|-----------|----|----|------|
| `uuid` | string | ✓ | エッジの一意識別子 |
| `source_node_uuid` | string | ✓ | 開始ノードのUUID |
| `target_node_uuid` | string | ✓ | 終了ノードのUUID |
| `name` | string | ✓ | 関係のタイプ（例: "WORKS_FOR", "LOCATED_IN"） |
| `fact` | string | ✓ | 関係の説明文（例: "山田太郎はABC株式会社で働いている"） |
| `created_at` | datetime | ✓ | エッジの作成日時 |
| `valid_at` | datetime | - | この情報が有効になった時刻 |
| `invalid_at` | datetime | - | この情報が無効になった時刻 |
| `expired_at` | datetime | - | この情報が期限切れになった時刻 |
| `episodes` | List[str] | ✓ | このFactを生成/更新したエピソードのUUIDリスト |
| `citations` | List[CitationInfo] | ✓ | 引用情報の配列 |
| `updated_at` | datetime | - | 最終更新日時 |
| `original_fact` | string | - | 元のFact（更新時に保存） |
| `update_reason` | string | - | 更新理由 |

### 時間情報の意味

Graphitiは**二重時間モデル (bi-temporal)** を採用しています：

- `created_at`: このエッジがGraphitiに追加された時刻
- `valid_at`: この関係が実際に有効になった時刻
- `invalid_at`: この関係が無効になった時刻（矛盾解消時に設定）
- `expired_at`: この関係が期限切れになった時刻（更新時に設定）

### エピソード参照

`episodes` 配列には、このFactを生成または更新したエピソードのUUIDが含まれます。
これにより、情報の出典を追跡できます。

### Edge データモデル

```python
class EntityEdge(BaseModel):
    """エンティティ間の関係"""
    uuid: str
    source_node_uuid: str
    target_node_uuid: str
    name: str
    fact: str
    created_at: datetime
    valid_at: Optional[datetime] = None
    invalid_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    episodes: List[str] = []
    citations: List[CitationInfo] = []
    # 修正履歴フィールド
    updated_at: Optional[datetime] = None
    original_fact: Optional[str] = None
    update_reason: Optional[str] = None
```

---

## Citation (引用情報) メタデータ

CitationはFactやNodeの出典情報を提供します。

### フィールド一覧

| フィールド | 型 | 必須 | 説明 |
|-----------|----|----|------|
| `episode_uuid` | string | ✓ | 参照元エピソードのUUID |
| `episode_name` | string | ✓ | 参照元エピソードの名前 |
| `source` | string | ✓ | ソースタイプ（"text", "json", "message"） |
| `source_description` | string | ✓ | ソースの説明（source_url埋め込み済み） |
| `created_at` | string | - | エピソードの作成日時（ISO 8601形式） |
| `source_url` | string | - | 抽出されたソースURL |

### Citation データモデル

```python
class CitationInfo(TypedDict):
    """引用情報"""
    episode_uuid: str
    episode_name: str
    source: str
    source_description: str
    created_at: str | None
    source_url: str | None  # source_descriptionから正規表現で抽出
```

### Citation Chain (引用チェーン)

Citation Chainは、エンティティの履歴を追跡します：

```python
class CitationChainEntry(TypedDict):
    """引用チェーンのエントリ"""
    episode_uuid: str
    episode_name: str
    source: str
    source_description: str
    created_at: str | None
    operation: str  # "created", "updated", "referenced"
    source_url: str | None
```

`operation` フィールドは、エピソードがエンティティに対して行った操作を示します：
- `created`: エンティティを作成した
- `updated`: エンティティを更新した
- `referenced`: エンティティを参照した

---

## Entity Types (エンティティタイプ定義)

Graphitiはカスタムエンティティタイプをサポートします。デフォルトでは以下のタイプが定義されています。

### デフォルトエンティティタイプ

| タイプ | 説明 | 優先度 | 抽出ルール |
|-------|------|--------|-----------|
| `Preference` | ユーザーの好み・選択 | 最高 | "I want", "I prefer", "I like" などのパターン |
| `Requirement` | 要件・必要事項 | 高 | "We need", "X is required", "must have" などのパターン |
| `Procedure` | 手順・プロセス | 中 | "First do X, then Y", "Always do X when Y" などのパターン |
| `Organization` | 組織・会社 | 中 | 会社名、機関名など |
| `Document` | ドキュメント | 中 | 書籍、記事、レポート、ビデオなど |
| `Event` | イベント・出来事 | 中 | 時間を持つ活動や出来事 |
| `Location` | 場所 | 低 | 物理的・仮想的な場所 |
| `Topic` | トピック・テーマ | 最低 | 会話のテーマ、関心領域 |
| `Object` | オブジェクト | 最低 | 物理的なアイテム、ツール |

### エンティティタイプの定義例

#### Requirement (要件)

```python
class Requirement(BaseModel):
    """要件を表すエンティティ

    Instructions for identifying and extracting requirements:
    1. Look for explicit statements of needs or necessities
    2. Identify functional specifications
    3. Pay attention to non-functional requirements (performance, security)
    4. Extract constraints or limitations
    5. Focus on clear, specific, and measurable requirements
    """
    project_name: str = Field(
        ...,
        description="The name of the project to which the requirement belongs.",
    )
    description: str = Field(
        ...,
        description="Description of the requirement.",
    )
```

#### Preference (優先事項)

```python
class Preference(BaseModel):
    """優先事項・好みを表すエンティティ

    IMPORTANT: Prioritize this classification over ALL other classifications.

    Trigger patterns: "I want/like/prefer/choose X", "I don't want/dislike/avoid/reject Y"
    """
    # Preferenceは属性を持たず、名前のみで識別される
    ...
```

### カスタムエンティティタイプの作成

config/config.yamlで定義:

```yaml
graphiti:
  entity_types:
    - name: "Task"
      description: |
        A Task represents a work item or action that needs to be completed.
        Instructions:
        1. Look for action items or TODOs
        2. Identify assignees and deadlines
        3. Capture task dependencies
```

---

## API リクエスト/レスポンス型

### Episode作成

```python
class EpisodeCreateRequest(BaseModel):
    """エピソード作成リクエスト"""
    name: str
    content: str
    group_id: Optional[str] = None
    source: Literal["text", "json", "message"] = "text"
    source_description: Optional[str] = ""
    source_url: Optional[str] = None
    uuid: Optional[str] = None

class EpisodeCreateResponse(BaseModel):
    """エピソード作成レスポンス"""
    status: str
    message: str
    episode_name: str
    group_id: str
```

### グラフ検索

```python
class GraphSearchRequest(BaseModel):
    """グラフ検索リクエスト"""
    query: str
    search_type: Literal["facts", "nodes", "episodes"] = "facts"
    max_results: int = Field(10, ge=1, le=100)
    group_ids: Optional[List[str]] = None
    entity_types: Optional[List[str]] = None  # ノード検索時のフィルタ
    center_node_uuid: Optional[str] = None  # Fact検索時の中心ノード

class GraphSearchResponse(BaseModel):
    """グラフ検索レスポンス"""
    message: str
    search_type: str
    results: List[Dict[str, Any]]
    count: int
```

### Fact更新

```python
class FactUpdateRequest(BaseModel):
    """Fact更新リクエスト"""
    fact: str
    source_node_uuid: Optional[str] = None
    target_node_uuid: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class FactUpdateResponse(BaseModel):
    """Fact更新レスポンス"""
    status: str
    old_uuid: str
    new_uuid: str
    message: str
    new_edge: Optional[Dict[str, Any]] = None
```

---

## 実装上の重要な設計パターン

### 1. source_url の埋め込みパターン

**なぜ独立したフィールドにしないのか？**

- Graphiti Coreはsource_urlフィールドをサポートしていない
- source_descriptionは自由形式の文字列フィールド
- 埋め込みパターンにより、既存のフィールドを活用できる

**埋め込み形式**:
```
"{original_description}, source_url: {url}"
```

**抽出正規表現**:
```python
r'source_url:\s*(https?://[^\s,]+)'
```

### 2. 時間情報の二重性

Graphitiは2種類の時間を管理します：

1. **システム時間** (`created_at`, `updated_at`): システムがデータを処理した時刻
2. **参照時間** (`reference_time`, `valid_at`): イベントが実際に発生した時刻

この二重性により、過去のイベントを遡って追加したり、時点指定クエリを実行できます。

### 3. 引用追跡

EdgeのepisodesフィールドにエピソードUUIDのリストを保持することで：

- 情報の出典を追跡
- 信頼性の評価
- 矛盾の検出と解消
- 監査証跡の提供

が可能になります。

### 4. Fact更新のソフトアップデート

Factを更新する際、古いFactを削除するのではなく：

1. 古いFactに `expired_at` を設定
2. 新しいFactを作成（新しいUUID）
3. 新しいFactは古いFactの `episodes` を継承

これにより、更新履歴を完全に保持できます。

---

## 参考資料

- [アーキテクチャドキュメント](./ARCHITECTURE.md)
- [データ取り込みガイド](./DATA_INGESTION.md)
- [Graphiti 公式ドキュメント](https://help.getzep.com/graphiti/)
- [graphiti-core GitHub](https://github.com/getzep/graphiti)

---

## バージョン履歴

- **1.0** (2025-11-29): 初版作成
  - Episode, Node, Edge, Citation のメタデータ仕様
  - Entity Types の詳細
  - API型定義
  - 実装パターンの説明

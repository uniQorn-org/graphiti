以下は、Zep社のOSS「Graphiti（getzep/graphiti）」の要点を、Neo4j＋OpenAI APIを使うあなたのPJ「uniQorn」向けに噛み砕いて整理したまとめです。

---

# Graphitiとは（ひとことで）

動的に変化するデータから**時間情報つきのナレッジグラフ**を自動構築・更新し、**ハイブリッド検索（埋め込み＋BM25＋グラフ探索）**で素早く引けるPython製フレームワーク。RAGよりも**更新頻度が高いデータ**や**エージェントの長期記憶**に向いている。([GitHub][1])

---

## 何が“普通のRAG／GraphRAG”と違うのか

* **リアルタイム増分更新**：新規データ（エピソード）を即時反映。バッチ再計算前提ではない。([GitHub][1])
* **二重時間モデル（bi-temporal）**：出来事の発生時刻と取り込み時刻を別トラックで保持。**時点指定クエリ**や**矛盾解消（エッジ無効化）**ができる。([GitHub][1])
* **ハイブリッド検索**：埋め込み・BM25・グラフトラバーサルを組み合わせ、RRFやMMR、クロスエンコーダで再ランク。通常サブ秒級の応答を狙う。([Zep Documentation][2])
* **柔軟なオントロジー**：Pydanticで**独自のエンティティ/エッジ型**を定義可。([Zep Documentation][3])

> 公式READMEでも**GraphRAG（MS系のバッチ寄り） vs Graphiti（連続更新前提）**の対比表が明記されている。([GitHub][1])

---

## コア概念（最低限これだけ）

* **Episode**：取り込み単位（テキスト/メッセージ/JSON）。出所・参照時刻を持つ。([Zep Documentation][4])
* **Entity / Fact（Edge）**：抽出された実体と関係。Factは**有効期間**を持ち、後発情報で**無効化**されうる。([ar5iv][5])
* **Community**：エンティティのクラスター。名称・要約を持ち、検索にも利用（動的更新だが**定期リフレッシュ推奨**）。([ar5iv][5])

---

## 公式要件と“最小構成”

* 言語：Python
* グラフDB：**Neo4j 5.26+**（AuraやDockerも可）
* LLM：**OpenAIがデフォルト**。他にAzure OpenAI/Gemini/Anthropic/Groq/Ollama等も選べる
* pip：`pip install graphiti-core`
* まずは **インデックス/制約の構築** → エピソード投入 → 検索、の順で動かす
* 429対策で**並列度(SEMAPHORE_LIMIT)**は控えめ既定。必要なら上げる
* 匿名テレメトリは`GRAPHITI_TELEMETRY_ENABLED=false`でOFF
  ([Zep Documentation][6])

---

## Neo4j＋OpenAIでの最小コード断片（uniQorn用の型は後述）

```python
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

graphiti = Graphiti("bolt://localhost:20687", "neo4j", "password")

# 初回のみ：Neo4j側にインデックス/制約を作成
await graphiti.build_indices_and_constraints()

# 1) エピソード投入（テキスト/JSONどちらもOK）
await graphiti.add_episode(
    name="incident_123",
    episode_body={"ticket_id": "INC-123", "service": "billing", "impact": "high"},
    source=EpisodeType.json,
    source_description="pagerduty webhook",
)

# 2) ハイブリッド検索（必要に応じて中心ノードで再ランク）
edges = await graphiti.search("billingで高優先度の障害の原因は？")
```

（APIや使い方はQuick Start／Searchingの記述通り）([Zep Documentation][6])

---

## uniQorn向けの実装指針（Neo4j＋OpenAI前提）

### 1) オントロジー（最初の叩き台）

* **Entity**：`User`, `Service`, `Incident`, `Runbook`, `Component`, `Vendor`
* **Edge/Fact**：`AFFECTS(User, Incident)`, `DEPENDS_ON(Service, Component)`, `ROOT_CAUSE_OF(Component, Incident)`, `REFERENCES(Runbook, Incident)`
* **属性**はPydanticモデルで追加（例：`Incident{severity, status, started_at, resolved_at}`）。([Zep Documentation][3])

### 2) 取り込み

* ユーザー対話、チケット、監視ログ、変更履歴、外部FAQ/Runbookを**エピソード**として逐次投入。
* **バルク取り込み**時は`add_episode_bulk`を使うが、**エッジ無効化は走らない**ので初期ロード専用に。([Zep Documentation][4])

### 3) 検索レシピ

* まず`EDGE_HYBRID_SEARCH_RRF`/`NODE_HYBRID_SEARCH_RRF`。情報が主体（Incident中心）なら中心ノードUUIDで**距離再ランク**。
* FAQ生成などは**クロスエンコーダ再ランク**（OpenAI/小型モデル）をオン。([Zep Documentation][2])

### 4) 生成フェーズ

* 検索で得た**Fact＋Entity要約**をプロンプトに整形→OpenAIで回答。
* “いつ時点の事実か”を**有効期間**付きで提示（誤読防止）。([Zep Documentation][2])

### 5) 運用TIPS

* **Neo4j**：本番はAuraDB/Enterpriseでの並列ランタイムも検討。CommunityでもOKだが性能余地は限定。([Zep Documentation][7])
* **並列度**：LLMのレート制限に合わせ`SEMAPHORE_LIMIT`調整。([Zep Documentation][6])
* **テレメトリ**：社内規約に合わせてOFF可。([Zep Documentation][6])
* **コミュニティ**：動的更新の精度は徐々にズレるので**定期リフレッシュ**を回す。([ar5iv][5])

---

## MCP連携（任意）

Claude DesktopやCursorなどと**MCPサーバー**でつなぎ、エージェントから`add_memory`/`search_facts`等のツールで直接読書き可。OpenAIキーとNeo4j設定を.envに置いて`uv run graphiti_mcp_server.py`で起動。([Zep Documentation][8])

---

## 既知の落とし穴

* **小型LLM**だと構造化出力が崩れやすい。OpenAI/Geminiなど**Structured Output対応**を推奨。AnthropicやGroq採用時でも**埋め込み/再ランクはOpenAI併用**が無難。([Zep Documentation][9])
* **バルク投入**は**エッジ無効化を行わない**（後続で矛盾解消が必要）。([Zep Documentation][4])
* **バージョン前提**：Neo4j 5.26+必須。([Zep Documentation][7])

---

## コミュニティ/実例（日本語）

* 技術調査・解説（Zenn）や手順メモが多数。**特性/二重時間/検索**の要点が整理されている。([Zenn][10])
* **LayerX**の事例紹介（法文書のインデックス）あり。実運用イメージの参考になる。([LayerX エンジニアブログ][11])
* Neo4j＋Gemini併用の私的ノートもあり（考え方の参考程度に）。([note（ノート）][12])

---

## 導入チェックリスト（uniQorn）

1. Neo4j 5.26+ を用意（AuraでもOK）。接続文字列・認証を環境変数に。([Zep Documentation][7])
2. `pip install graphiti-core`、`OPENAI_API_KEY`設定。([Zep Documentation][6])
3. 初回に`build_indices_and_constraints()`を実行。([Zep Documentation][6])
4. チケット/対話/Runbook/監視ログを**Episode**として投入（初期は`add_episode_bulk`、運用は`add_episode`）。([Zep Documentation][4])
5. `*_HYBRID_SEARCH_*`レシピ＋中心ノード再ランクで検索→OpenAIに渡して回答生成。([Zep Documentation][2])
6. 429が出たら**SEMAPHORE_LIMIT**/スループットを調整。([Zep Documentation][6])
7. 定期的にCommunity再計算、グラフ健全性チェック。([ar5iv][5])

---

### ライセンス

* ライセンス：Apache-2.0


[1]: https://github.com/getzep/graphiti "GitHub - getzep/graphiti: Build Real-Time Knowledge Graphs for AI Agents"
[2]: https://help.getzep.com/graphiti/working-with-data/searching "Searching the Graph | Zep Documentation"
[3]: https://help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types "Custom Entity and Edge Types | Zep Documentation"
[4]: https://help.getzep.com/graphiti/core-concepts/adding-episodes "Adding Episodes | Zep Documentation"
[5]: https://ar5iv.org/abs/2501.13956 "[2501.13956] Zep: A Temporal Knowledge Graph Architecture for Agent Memory"
[6]: https://help.getzep.com/graphiti/getting-started/quick-start "Quick Start | Zep Documentation"
[7]: https://help.getzep.com/graphiti/configuration/neo-4-j-configuration "Neo4j Configuration | Zep Documentation"
[8]: https://help.getzep.com/graphiti/getting-started/mcp-server "Knowledge Graph MCP Server | Zep Documentation"
[9]: https://help.getzep.com/graphiti/configuration/llm-configuration "LLM Configuration | Zep Documentation"
[10]: https://zenn.dev/suwash/articles/graphithi_20250605?utm_source=chatgpt.com "技術調査 - Graphiti - Zenn"
[11]: https://tech.layerx.co.jp/entry/2025/10/07/095559?utm_source=chatgpt.com "【Agent Memory】Graphitiで法文書のインデックスを構築する"
[12]: https://note.com/major_elk2890/n/n0b7e32046c28?utm_source=chatgpt.com "GraphitiとNeo4jとGemini 2.5＋AIで構築する次世代知識グラフ ..."

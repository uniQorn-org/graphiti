# Graphiti Search Bot Frontend

Reactで構築された社内検索Botのフロントエンド

## 機能

### 1. チャットインターフェース

- AIとの対話形式で情報を検索
- 検索結果がリアルタイムで表示
- チャット履歴の保持

### 2. 手動検索

- キーワードベースのナレッジグラフ検索
- エンティティと関係性の表示

### 3. Fact編集

- 検索結果から間違ったFactsを発見
- クリックして修正可能
- 修正理由の記録

## 技術スタック

- React 18
- TypeScript
- Vite
- Axios

## セットアップ

```bash
cd frontend
npm install
npm run dev
```

## 環境変数

- `VITE_API_BASE_URL`: バックエンドAPIのURL (デフォルト: http://localhost:20001/api)

## ビルド

```bash
npm run build
```

## Docker

```bash
docker build -t search-bot-frontend .
docker run -p 20002:20002 search-bot-frontend
```

## 画面構成

### チャットタブ

- メッセージ入力エリア
- チャット履歴表示
- 検索結果パネル (右側)
  - エッジ (Facts) リスト
  - ノード (エンティティ) リスト
  - 各Factに「修正」ボタン

### 検索タブ

- 検索キーワード入力
- 検索結果表示
- Fact編集機能

## 使い方

1. **チャットで質問**
   - 「山田さんの役割は？」などと入力
   - AIが検索結果をもとに回答
   - 右パネルに関連するFactsが表示

2. **Factの修正**
   - 表示されたFactの「修正」ボタンをクリック
   - モーダルで新しいFactを入力
   - 修正理由を記入（任意）
   - 保存

3. **手動検索**
   - 検索タブに切り替え
   - キーワードを入力して検索
   - 結果からFactを修正可能

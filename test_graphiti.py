#!/usr/bin/env python3
"""
Graphiti MCP システムの動作テスト
"""
import asyncio
import sys
from datetime import datetime
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType


async def test_graphiti():
    print("🚀 Graphiti MCP システムのテストを開始します...")
    print()

    # Graphitiクライアントを初期化
    print("📊 Graphitiクライアントを初期化中...")
    # Docker内部では neo4j ホスト名を使用、ホストからは localhost
    import os
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    client = Graphiti(
        uri=neo4j_uri,
        user="neo4j",
        password="password123"
    )

    try:
        # エピソードを追加
        print("✏️  エピソード1を追加中...")
        await client.add_episode(
            name="meeting_2024_01_15",
            episode_body="2024年1月15日の会議で、新しいAI機能の開発計画を議論しました。山田さんがプロジェクトリーダーに任命され、佐藤さんがバックエンド開発を担当することになりました。",
            source_description="定例会議の議事録",
            reference_time=datetime(2024, 1, 15, 14, 0)
        )
        print("✅ エピソード1を追加しました")
        print()

        print("✏️  エピソード2を追加中...")
        await client.add_episode(
            name="development_update_2024_01_20",
            episode_body="1月20日、山田さんのチームがAI機能の最初のプロトタイプを完成させました。佐藤さんが実装したAPIエンドポイントは性能テストで良好な結果を示しました。",
            source_description="開発進捗レポート",
            reference_time=datetime(2024, 1, 20, 10, 0)
        )
        print("✅ エピソード2を追加しました")
        print()

        print("✏️  エピソード3を追加中...")
        await client.add_episode(
            name="project_completion_2024_02_01",
            episode_body="2月1日、AI機能プロジェクトが無事完了しました。山田さんと佐藤さんのチームワークが成功の鍵でした。新機能は来週リリース予定です。",
            source_description="プロジェクト完了報告",
            reference_time=datetime(2024, 2, 1, 16, 0)
        )
        print("✅ エピソード3を追加しました")
        print()

        # 検索テスト
        print("🔍 検索テスト1: '山田さん'を検索中...")
        results1 = await client.search("山田さんの役割は何ですか？")
        print(f"📝 検索結果: {results1}")
        print()

        print("🔍 検索テスト2: 'AI機能'を検索中...")
        results2 = await client.search("AI機能の開発状況")
        print(f"📝 検索結果: {results2}")
        print()

        print("🔍 検索テスト3: '佐藤さん'を検索中...")
        results3 = await client.search("佐藤さんは何を担当しましたか？")
        print(f"📝 検索結果: {results3}")
        print()

        print("✅ テスト完了！Graphitiは正常に動作しています。")
        print()
        print("📊 Neo4jブラウザで結果を確認できます:")
        print("   URL: http://localhost:7474")
        print("   ユーザー名: neo4j")
        print("   パスワード: password123")
        print()
        print("   次のクエリを実行してグラフを表示:")
        print("   MATCH (n) RETURN n LIMIT 25")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # クライアントを閉じる
        await client.close()
        print()
        print("👋 Graphitiクライアントを閉じました")


if __name__ == "__main__":
    asyncio.run(test_graphiti())
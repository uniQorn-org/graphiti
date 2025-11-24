"""
データモデル定義
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EntityNode(BaseModel):
    """エンティティノード"""
    uuid: str
    name: str
    summary: Optional[str] = None
    created_at: datetime
    labels: List[str] = []
    attributes: Dict[str, Any] = {}


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
    # 修正履歴フィールド
    updated_at: Optional[datetime] = None
    original_fact: Optional[str] = None
    update_reason: Optional[str] = None


class SearchResult(BaseModel):
    """検索結果"""
    nodes: List[EntityNode] = []
    edges: List[EntityEdge] = []
    total_count: int = 0


class ChatMessage(BaseModel):
    """チャットメッセージ"""
    role: str = Field(..., description="user or assistant")
    content: str


class ChatRequest(BaseModel):
    """チャットリクエスト"""
    message: str
    history: List[ChatMessage] = []
    include_search_results: bool = True


class ChatResponse(BaseModel):
    """チャットレスポンス"""
    answer: str
    search_results: Optional[SearchResult] = None
    sources: List[str] = []


class ManualSearchRequest(BaseModel):
    """手動検索リクエスト"""
    query: str
    limit: int = 10


class UpdateFactRequest(BaseModel):
    """Fact更新リクエスト"""
    edge_uuid: str
    new_fact: str
    reason: Optional[str] = None


class UpdateFactResponse(BaseModel):
    """Fact更新レスポンス"""
    success: bool
    message: str
    updated_edge: Optional[EntityEdge] = None


class AddEpisodeRequest(BaseModel):
    """エピソード追加リクエスト"""
    name: str
    content: str
    source: str = "user_input"
    source_description: Optional[str] = None


class AddEpisodeResponse(BaseModel):
    """エピソード追加レスポンス"""
    success: bool
    message: str
    episode_uuid: Optional[str] = None
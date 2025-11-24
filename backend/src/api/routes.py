"""
APIルート定義
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    ManualSearchRequest,
    SearchResult,
    UpdateFactRequest,
    UpdateFactResponse,
    AddEpisodeRequest,
    AddEpisodeResponse,
)
from ..services import GraphitiService, LangChainService
from ..config import get_graphiti_service, get_langchain_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    langchain_service: LangChainService = Depends(get_langchain_service),
):
    """
    チャットエンドポイント

    Args:
        request: チャットリクエスト

    Returns:
        チャット応答
    """
    try:
        response = await langchain_service.chat(
            message=request.message,
            history=request.history,
            include_search_results=request.include_search_results,
        )
        return response
    except Exception as e:
        logger.error(f"チャットエラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResult)
async def search(
    request: ManualSearchRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
):
    """
    手動検索エンドポイント

    Args:
        request: 検索リクエスト

    Returns:
        検索結果
    """
    try:
        results = await graphiti_service.search(
            query=request.query, limit=request.limit
        )
        return results
    except Exception as e:
        logger.error(f"検索エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/facts/{edge_uuid}", response_model=UpdateFactResponse)
async def update_fact(
    edge_uuid: str,
    request: UpdateFactRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
):
    """
    Fact更新エンドポイント

    Args:
        edge_uuid: エッジUUID
        request: 更新リクエスト

    Returns:
        更新結果
    """
    try:
        # リクエストのedge_uuidを使用
        result = await graphiti_service.update_fact(
            edge_uuid=edge_uuid, new_fact=request.new_fact, reason=request.reason
        )
        return result
    except Exception as e:
        logger.error(f"Fact更新エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/episodes", response_model=AddEpisodeResponse)
async def add_episode(
    request: AddEpisodeRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
):
    """
    エピソード追加エンドポイント

    Args:
        request: エピソード追加リクエスト

    Returns:
        追加結果
    """
    try:
        result = await graphiti_service.add_episode(
            name=request.name,
            content=request.content,
            source=request.source,
            source_description=request.source_description,
        )
        return result
    except Exception as e:
        logger.error(f"エピソード追加エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "service": "search-bot-backend"}
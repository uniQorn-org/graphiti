"""
API route definitions
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
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
    Chat endpoint

    Args:
        request: Chat request

    Returns:
        Chat response
    """
    try:
        response = await langchain_service.chat(
            message=request.message,
            history=request.history,
            include_search_results=request.include_search_results,
        )
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResult)
async def search(
    request: ManualSearchRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
):
    """
    Manual search endpoint

    Args:
        request: Search request

    Returns:
        Search results
    """
    try:
        results = await graphiti_service.search(
            query=request.query, limit=request.limit
        )
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/facts/{edge_uuid}", response_model=UpdateFactResponse)
async def update_fact(
    edge_uuid: str,
    request: UpdateFactRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
):
    """
    Fact update endpoint

    Args:
        edge_uuid: Edge UUID
        request: Update request

    Returns:
        Update result
    """
    try:
        # Use edge_uuid from request
        result = await graphiti_service.update_fact(
            edge_uuid=edge_uuid, new_fact=request.new_fact, reason=request.reason
        )
        return result
    except Exception as e:
        logger.error(f"Fact update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/episodes", response_model=AddEpisodeResponse)
async def add_episode(
    request: AddEpisodeRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
):
    """
    Episode addition endpoint

    Args:
        request: Episode addition request

    Returns:
        Addition result
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
        logger.error(f"Episode addition error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "search-bot-backend"}
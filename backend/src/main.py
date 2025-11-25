"""
FastAPIメインアプリケーション
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
from .config import get_settings, init_services, shutdown_services

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理"""
    # 起動時
    logger.info("サービスを初期化中...")
    await init_services()
    logger.info("サービスの初期化が完了しました")
    yield
    # シャットダウン時
    logger.info("サービスをシャットダウン中...")
    await shutdown_services()
    logger.info("サービスのシャットダウンが完了しました")


# FastAPIアプリケーション作成
app = FastAPI(
    title="Graphiti Search Bot API",
    description="LangChain + Graphitiを使った社内検索Bot",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定
settings = get_settings()
origins = settings.cors_origins.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "service": "Graphiti Search Bot API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.backend_port,
        reload=True,
        log_level="info",
    )

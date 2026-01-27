import logging
import uvicorn
from fastapi import FastAPI

from orchestrator.middleware import configure_middleware
from orchestrator.exception_handlers import unhandled_exception_handler
from orchestrator.lifespan import lifespan
from orchestrator.apis.conversations.router import conversation_router
from orchestrator.apis.meta.router import meta_router
from orchestrator.config import app_cfg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

api = FastAPI(
    title="DevConf Multi-Agent API",
    description="DevConf Multi-Agent System",
    version="0.1.0",
    exception_handlers={
        Exception: unhandled_exception_handler
    },
    lifespan=lifespan
)

api = configure_middleware(api)

api.include_router(meta_router, prefix=app_cfg.API_ROUTER_PATH_PREFIX)
api.include_router(conversation_router, prefix=app_cfg.API_ROUTER_PATH_PREFIX)

if __name__ == '__main__':
    uvicorn.run(
        app="orchestrator.main:api",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


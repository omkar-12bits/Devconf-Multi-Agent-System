import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from orchestrator.config import app_cfg
from orchestrator.supervisor import create_supervisor

logger = logging.getLogger(__name__)


async def run_startup_dependencies(app: FastAPI) -> None:
    """Initialize all application dependencies at startup."""
    logger.info("Starting DevConf Multi-Agent API")
    if app_cfg.OPENAI_API_KEY:
        os.environ['OPENAI_API_KEY'] = app_cfg.OPENAI_API_KEY
        logger.info("OpenAI API key configured")
    else:
        logger.error("OPENAI_API_KEY not found in configuration!")
        logger.error("  Please set OPENAI_API_KEY in your .env file")
        raise ValueError("OPENAI_API_KEY is required")
    
    logger.info("Initializing session service...")
    session_service = InMemorySessionService()
    logger.info("Session service initialized")
    
    logger.info("Creating supervisor agent...")
    supervisor = create_supervisor()
    logger.info("Supervisor agent created")
    
    logger.info("Creating ADK runner with supervisor workflow...")
    runner = Runner(
        agent=supervisor.supervisor_agent,
        app_name=app_cfg.APP_NAME,
        session_service=session_service
    )
    logger.info("ADK runner created with supervisor workflow")
    app.state.runner = runner
    app.state.session_service = session_service
    app.state.supervisor = supervisor
    app.state.app_name = app_cfg.APP_NAME
    
    logger.info("All systems initialized successfully")
    logger.info("API ready to accept requests")


async def shutdown_dependencies(app: FastAPI) -> None:
    """Cleanup all application dependencies at shutdown."""
    logger.info("Shutting down DevConf Multi-Agent API...")
    logger.info("Cleaning up resources...")
    
    try:
        if hasattr(app.state, 'runner'):
            app.state.runner = None
            logger.info("ADK runner cleaned up")
        
        if hasattr(app.state, 'supervisor'):
            app.state.supervisor = None
            logger.info("Supervisor agent cleaned up")
        
        logger.info("All resources cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown)."""
    try:
        await run_startup_dependencies(app)
        yield
        await shutdown_dependencies(app)
        
    except Exception as e:
        logger.error(f"Error in lifespan management: {e}", exc_info=True)
        raise


import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, DatabaseSessionService

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
    
    # Choose session service based on configuration
    if app_cfg.USE_DATABASE_SESSIONS and app_cfg.DATABASE_URL:
        logger.info("Using DatabaseSessionService with MariaDB")
        db_url_display = app_cfg.DATABASE_URL.split('@')[1] if '@' in app_cfg.DATABASE_URL else 'configured'
        logger.info(f"Database URL: {db_url_display}")
        try:
            session_service = DatabaseSessionService(db_url=app_cfg.DATABASE_URL)
            logger.info("DatabaseSessionService initialized - conversations will persist in database")
        except Exception as e:
            logger.error(f"Failed to initialize DatabaseSessionService: {e}")
            logger.warning("Falling back to InMemorySessionService")
            session_service = InMemorySessionService()
    else:
        logger.info("Using InMemorySessionService (sessions will not persist)")
        if not app_cfg.USE_DATABASE_SESSIONS:
            logger.info("  To enable database persistence, set USE_DATABASE_SESSIONS=true")
        if not app_cfg.DATABASE_URL:
            logger.info("  To enable database persistence, set DATABASE_URL in .env")
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
        if hasattr(app.state, 'session_service'):
            session_service = app.state.session_service
            
            if isinstance(session_service, DatabaseSessionService):
                logger.info("Disposing database connection pool...")
                try:
                    if hasattr(session_service, 'db_engine'):
                        session_service.db_engine.dispose()
                        logger.info("Database connection pool disposed successfully")
                    else:
                        logger.warning("DatabaseSessionService has no db_engine attribute")
                except Exception as e:
                    logger.error(f"Error disposing database engine: {e}", exc_info=True)
            else:
                logger.info("Using InMemorySessionService - no database cleanup needed")
        
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


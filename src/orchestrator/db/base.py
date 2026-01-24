import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from orchestrator.config import app_cfg

logger = logging.getLogger(__name__)


def make_database_url():
    """
    Create database URL from configuration.
    
    Returns:
        Database URL string for SQLAlchemy
    """
    return app_cfg.DATABASE_URL


if app_cfg.DATABASE_URL and app_cfg.USE_DATABASE_SESSIONS:
    db_engine = create_engine(make_database_url(), pool_pre_ping=True)
    DatabaseSession = sessionmaker(bind=db_engine)
else:
    db_engine = None
    DatabaseSession = None

Base = declarative_base()


def db_connection_check():
    """
    Check if database connection is working.
    
    Returns:
        True if connection successful, False otherwise
    """
    if DatabaseSession is None:
        return False

    try:
        from sqlalchemy import text
        with DatabaseSession() as db_session:
            db_session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.warning(f"Database connection check failure: {e}")
        return False

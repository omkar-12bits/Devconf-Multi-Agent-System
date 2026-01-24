from sqlalchemy import Column, String, Text, DateTime, Boolean
from orchestrator.db.base import Base


class Event(Base):
    """
    SQLAlchemy model for events table (created and managed by Google ADK).
    
    READ-ONLY MODEL:
    - Do not use for INSERT/UPDATE/DELETE operations
    - Google ADK manages this table
    """
    
    __tablename__ = "events"

    id = Column(String(128), primary_key=True)
    app_name = Column(String(128), primary_key=True)
    user_id = Column(String(128), primary_key=True)
    session_id = Column(String(128), primary_key=True)
    invocation_id = Column(String(256), nullable=False)
    author = Column(String(256), nullable=False)
    timestamp = Column(DateTime(6), nullable=False)
    content = Column(Text)
    custom_metadata = Column(Text)
    branch = Column(String(256))
    partial = Column(Boolean)
    turn_complete = Column(Boolean)
    error_message = Column(String(1024))

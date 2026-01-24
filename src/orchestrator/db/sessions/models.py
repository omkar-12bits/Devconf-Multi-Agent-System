from sqlalchemy import Column, String, DateTime, Text
from orchestrator.db.base import Base


class Session(Base):
    """
    SQLAlchemy model for sessions table (created and managed by Google ADK).
    
    READ-ONLY MODEL - Google ADK manages this table.
    """
    
    __tablename__ = "sessions"
    
    app_name = Column(String(128), primary_key=True)
    user_id = Column(String(128), primary_key=True)
    id = Column(String(128), primary_key=True)
    state = Column(Text, nullable=False)
    create_time = Column(DateTime(6), nullable=False)
    update_time = Column(DateTime(6), nullable=False)

from sqlalchemy import Column, String, Enum, Text, TIMESTAMP, text

from orchestrator.db.base import Base


class Feedback(Base):
    """SQLAlchemy model for feedback table."""
    
    __tablename__ = "feedback"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), nullable=False)
    invocation_id = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=False)
    feedback_type = Column(Enum('positive', 'negative', name='feedback_type_enum'), nullable=False)
    comment = Column(Text)
    predefined_response = Column(String(500))
    source_agent = Column(String(100))
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))

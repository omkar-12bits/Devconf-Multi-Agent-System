import logging
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Annotated

from orchestrator.apis.history.models import HistoryResponse, SessionDetail
from orchestrator.apis.history.service import get_history_service
from orchestrator.apis.models import User
from orchestrator.apis.auth import user_authorization

logger = logging.getLogger(__name__)

history_router = APIRouter(tags=["History"])


@history_router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Get conversation history",
    description="Retrieve the last N conversation sessions with their metadata for the authenticated user"
)
async def get_conversation_history(
    user: Annotated[User, Depends(user_authorization)],
    limit: Annotated[int, Query(
        ge=1, 
        le=50,
        description="Maximum number of sessions to return (1-50)"
    )] = 10
) -> HistoryResponse:
    """
    Get conversation history."""
    try:
        logger.info(f"Fetching history for user {user.id}, limit={limit}")
        
        try:
            history_service = get_history_service()
        except ValueError as ve:
            logger.error(f"History service configuration error: {ve}")
            raise HTTPException(
                status_code=500,
                detail="History feature not available. Database storage is not enabled."
            )
        
        sessions = history_service.get_user_sessions(
            user_id=user.id,
            limit=limit
        )
        
        logger.info(f"Successfully retrieved {len(sessions)} sessions for user {user.id}")
        
        return HistoryResponse(
            sessions=sessions,
            total_count=len(sessions)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch conversation history: {str(e)}"
        )


@history_router.get(
    "/history/{conversation_id}",
    response_model=SessionDetail,
    summary="Get specific conversation history",
    description="Retrieve complete conversation history with all turns for a specific conversation"
)
async def get_conversation_history(
    conversation_id: Annotated[str, Path(
        description="Conversation ID to retrieve",
        examples=["358a9020-81df-45fa-a61e-37a911f977c8"]
    )],
    user: Annotated[User, Depends(user_authorization)]
) -> SessionDetail:
    """
    Get conversation history for a specific conversation."""
    try:
        logger.info(f"Fetching conversation {conversation_id} for user {user.id}")
        
        try:
            history_service = get_history_service()
        except ValueError as ve:
            logger.error(f"History service configuration error: {ve}")
            raise HTTPException(
                status_code=500,
                detail="History feature not available. Database storage is not enabled."
            )
        
        session = history_service.get_session_detail_by_id(
            session_id=conversation_id,
            user_id=user.id
        )
        
        if not session:
            logger.warning(f"Conversation {conversation_id} not found for user {user.id}")
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found or you don't have access to it"
            )
        
        logger.info(
            f"Successfully retrieved conversation {conversation_id} with {session.turn_count} turns"
        )
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error fetching conversation {conversation_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch conversation history: {str(e)}"
        )


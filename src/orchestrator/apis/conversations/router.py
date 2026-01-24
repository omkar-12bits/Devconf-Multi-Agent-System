import logging
import uuid
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from google.genai import types
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from typing import Annotated

from orchestrator.apis.conversations.models import (
    NewConversationResponse,
    MessageRequest,
    MessageChunkResponse
)
from orchestrator.apis.models import User
from orchestrator.apis.auth import user_authorization
from orchestrator.utils.app_utils import process_event_data, aggregate_events_text

logger = logging.getLogger(__name__)

conversation_router = APIRouter(prefix="/conversation", tags=["conversation"])


@conversation_router.post(
    "",
    response_model=NewConversationResponse,
    description="Create a new conversation and get the new conversation's ID",
    operation_id="createConversation"
)
async def new_conversation(
    request: Request,
    user: Annotated[User, Depends(user_authorization)]
):
    """Create a new conversation session."""
    try:
        conversation_id = str(uuid.uuid4())
        user_id = user.id
        
        session_service = request.app.state.session_service
        app_name = request.app.state.app_name
        
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=conversation_id
        )
        
        logger.info(f"Created conversation: {conversation_id} for user: {user.username} (ID: {user_id})")
        
        return NewConversationResponse(
            conversation_id=conversation_id,
            user_id=user_id,
            app_name=app_name
        )
    except Exception as e:
        logger.exception("Failed to create conversation session")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create conversation session"
        )


@conversation_router.post(
    "/{conversation_id}/message",
    response_model=MessageChunkResponse,
    description="Send a new message in existing conversation",
    operation_id="createMessage"
)
async def post_message(
    conversation_id: str,
    message: MessageRequest,
    request: Request,
    user: Annotated[User, Depends(user_authorization)]
) -> StreamingResponse | MessageChunkResponse:
    """Send a new message in existing conversation.
    
    Supports both streaming and non-streaming responses based on message.stream flag.
    """
    user_id = user.id
    
    # Access dependencies from app state
    session_service = request.app.state.session_service
    runner = request.app.state.runner
    app_name = request.app.state.app_name
    
    logger.info(f"Received message for conversation_id={conversation_id} from user: {user.username} streaming={message.stream}")
    
    try:
        # Ensure the conversation exists
        session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=conversation_id
        )
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation not found: {conversation_id}"
            )
        
        if message.stream:
            async def event_generator():
                try:
                    content = types.Content(
                        role="user",
                        parts=[types.Part(text=message.input)]
                    )
                    
                    last_message_id = None
                    
                    async for event in runner.run_async(
                        user_id=user_id,
                        session_id=conversation_id,
                        new_message=content
                    ):
                        if event.invocation_id:
                            last_message_id = event.invocation_id
                        
                        event_data = process_event_data(event, conversation_id)
                        yield f"data: {json.dumps(event_data.model_dump(exclude_none=True))}\n\n"

                    yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'message_id': last_message_id, 'event_type': 'done'})}\n\n"

                except Exception as e:
                    logger.error(f"Error during streaming for conversation {conversation_id}: {e}", exc_info=True)
                    error_data = {
                        "error": str(e),
                        "conversation_id": conversation_id,
                        "message_id": last_message_id,
                        "event_type": "error"
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Non-streaming: buffer the complete response
            content = types.Content(
                role="user",
                parts=[types.Part(text=message.input)]
            )
            
            buffered_response = ""
            event_thinking = ""
            final_message_id = None
            
            async for event in runner.run_async(
                user_id=user_id,
                session_id=conversation_id,
                new_message=content
            ):
                if event.invocation_id:
                    final_message_id = event.invocation_id
                
                buffered_response, event_thinking = aggregate_events_text(
                    event,
                    buffered_response,
                    event_thinking
                )
            
            return MessageChunkResponse(
                content=buffered_response or "No response generated",
                conversation_id=conversation_id,
                message_id=final_message_id,
                user_id=user_id,
                thinking=event_thinking,
                done=True
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception("Failed to process message")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI assistant is not able to process the message"
        )


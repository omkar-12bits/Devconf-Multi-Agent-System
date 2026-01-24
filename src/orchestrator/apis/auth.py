from fastapi import Header
from typing import Annotated, Optional
from orchestrator.apis.models import User

async def user_authorization(
    user_id: Annotated[Optional[str], Header()] = None,
) -> User:
    """
    Simple authentication dependency.
    For the open source version, this accepts user info from headers
    or falls back to a default test user.
    """
    
    if not user_id:
        # Fallback for testing/local dev
        return User(
            id="test-user-id",
            access_token="mock-token",
            token_claims={},
            username="testuser",
            email="test@example.com"
        )
        
    return User(
        id=user_id,
        access_token="mock-token",
        token_claims={},
        username="testuser",
        email=None
    )

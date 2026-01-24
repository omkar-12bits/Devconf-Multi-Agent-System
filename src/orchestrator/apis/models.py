from pydantic import BaseModel, Field
from typing import Dict


class User(BaseModel):
    """The user object associated with an API request."""
    
    id: str = Field(
        description="User unique ID (`user_id`) based on JWT access token."
    )
    access_token: str = Field(
        description="User's JWT access token value."
    )
    token_claims: Dict = Field(
        description="Decoded JWT access token claims."
    )
    username: str = Field(
        description="`username` or if not available, `preferred_username` from JWT access token."
    )
    email: str | None = Field(
        default=None,
        description="User's email based on JWT access token."
    )


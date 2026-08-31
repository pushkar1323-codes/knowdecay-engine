"""
app/schemas/auth.py
────────────────────
Pydantic schemas for authentication endpoints.
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Email/password login credentials."""
    email: str = Field(..., description="User email address", examples=["student@example.com"])
    password: str = Field(..., min_length=8, description="User password", examples=["SecureP@ss123"])


class TokenResponse(BaseModel):
    """JWT token pair returned on successful authentication."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Access token expiry in seconds")


class RefreshRequest(BaseModel):
    """Request to refresh an access token."""
    refresh_token: str = Field(..., description="Current valid refresh token")


class PasswordChangeRequest(BaseModel):
    """Request to change the authenticated user's password."""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (min 8 chars)")


class MessageResponse(BaseModel):
    """Simple message response for actions like logout."""
    message: str = Field(..., description="Result message")

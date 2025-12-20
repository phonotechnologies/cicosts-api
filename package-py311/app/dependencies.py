"""
CICosts API - Dependencies

Reusable FastAPI dependencies for authentication, etc.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.database import get_db
from app.config import get_api_secrets
from app.models.user import User


# Security scheme
security = HTTPBearer(auto_error=False)


class CurrentUser:
    """Current authenticated user context."""

    def __init__(
        self,
        user_id: UUID,
        email: str,
        github_login: str,
        github_id: Optional[int] = None,
    ):
        self.user_id = user_id
        self.email = email
        self.github_login = github_login
        self.github_id = github_id


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[CurrentUser]:
    """
    Get current user from JWT token (optional).

    Returns None if no valid token is provided.
    """
    if not credentials:
        return None

    token = credentials.credentials
    api_secrets = get_api_secrets()
    jwt_secret = api_secrets.get("jwt_secret", "changeme")

    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("user_id")

        if not user_id:
            return None

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            return None

        return CurrentUser(
            user_id=UUID(user_id),
            email=payload.get("email", ""),
            github_login=payload.get("github_login", ""),
            github_id=payload.get("github_id"),
        )
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    Get current user from JWT token (required).

    Raises 401 if no valid token is provided.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    api_secrets = get_api_secrets()
    jwt_secret = api_secrets.get("jwt_secret", "changeme")

    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return CurrentUser(
            user_id=UUID(user_id),
            email=payload.get("email", ""),
            github_login=payload.get("github_login", ""),
            github_id=payload.get("github_id"),
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_with_db(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, Session]:
    """
    Get current user model and database session.

    Useful when you need to update user data.
    """
    user = db.query(User).filter(
        User.id == current_user.user_id,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user, db

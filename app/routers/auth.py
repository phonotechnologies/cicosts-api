"""
Authentication endpoints.

GitHub OAuth flow for user login.
Reference: spec-data-lifecycle.md § 5 (multi-org model)
"""
import secrets
import httpx
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt
from pydantic import BaseModel

from app.database import get_db
from app.config import settings, get_github_secrets, get_api_secrets
from app.models.user import User
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.dependencies import get_current_user, CurrentUser

router = APIRouter()

# In-memory state storage (use Redis in production)
_oauth_states: dict = {}


async def _get_github_org_role(access_token: str, org_login: str, username: str) -> str:
    """
    Get user's role in a GitHub organization.

    Queries GitHub's membership API to determine if user is admin/owner or member.
    Returns "owner" for org admins, "member" for regular members.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/orgs/{org_login}/memberships/{username}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        if response.status_code == 200:
            membership = response.json()
            # GitHub returns "admin" for org owners/admins, "member" for regular members
            # We map "admin" to "owner" to match our database terminology
            if membership.get("role") == "admin":
                return "owner"

        # Default to member if we can't determine the role
        return "member"


class UserResponse(BaseModel):
    """User response schema."""
    id: str
    email: str
    github_login: Optional[str]
    github_id: Optional[int]
    github_avatar_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationResponse(BaseModel):
    """Organization response schema."""
    id: str
    github_org_slug: str
    github_org_name: Optional[str]
    role: str


class MeResponse(BaseModel):
    """Current user with organizations."""
    user: UserResponse
    organizations: list[OrganizationResponse]


@router.get("/login")
async def github_login(
    redirect_uri: Optional[str] = Query(None),
):
    """
    Initiate GitHub OAuth flow.

    Redirects user to GitHub for authorization.
    """
    github_secrets = get_github_secrets()
    client_id = settings.GITHUB_CLIENT_ID or github_secrets.get("client_id", "")

    if not client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    # Generate state token
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "redirect_uri": redirect_uri or settings.FRONTEND_URL,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Clean up old states (older than 10 minutes)
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    expired = [
        k for k, v in _oauth_states.items()
        if datetime.fromisoformat(v["created_at"]) < cutoff
    ]
    for k in expired:
        _oauth_states.pop(k, None)

    # GitHub OAuth URL
    github_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&scope=read:user read:org"
        f"&state={state}"
        f"&redirect_uri={settings.API_URL}/api/v1/auth/callback"
    )

    return RedirectResponse(url=github_url)


@router.get("/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    GitHub OAuth callback.

    - Exchange code for access token
    - Fetch user info from GitHub
    - Create or update user in database
    - Create organization and membership
    - Return JWT token
    """
    # Validate state (graceful fallback for serverless environments)
    # In Lambda, the instance that created the state may differ from callback handler
    if state in _oauth_states:
        state_data = _oauth_states.pop(state)
        redirect_uri = state_data["redirect_uri"]
    else:
        # Fallback to frontend URL - GitHub still validates state on their end
        redirect_uri = settings.FRONTEND_URL

    # Get secrets
    github_secrets = get_github_secrets()
    api_secrets = get_api_secrets()

    client_id = settings.GITHUB_CLIENT_ID or github_secrets.get("client_id", "")
    client_secret = github_secrets.get("client_secret", "")
    jwt_secret = api_secrets.get("jwt_secret", "changeme")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            error = token_data.get("error_description", "No access token received")
            raise HTTPException(status_code=400, detail=error)

        # Fetch user info
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")

        github_user = user_response.json()

        # Fetch user's organizations
        orgs_response = await client.get(
            "https://api.github.com/user/orgs",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        github_orgs = orgs_response.json() if orgs_response.status_code == 200 else []

    # Create or update user
    user = db.query(User).filter(User.github_id == github_user["id"]).first()

    if user:
        # Update existing user
        user.github_login = github_user["login"]
        user.github_avatar_url = github_user.get("avatar_url")
        user.github_access_token = access_token  # TODO: encrypt this
        if github_user.get("email"):
            user.email = github_user["email"]
    else:
        # Create new user
        user = User(
            id=uuid4(),
            email=github_user.get("email") or f"{github_user['login']}@users.noreply.github.com",
            github_id=github_user["id"],
            github_login=github_user["login"],
            github_avatar_url=github_user.get("avatar_url"),
            github_access_token=access_token,  # TODO: encrypt this
        )
        db.add(user)
        db.flush()

    # Create organizations for each GitHub org (if not exists)
    for gh_org in github_orgs:
        org = db.query(Organization).filter(
            Organization.github_org_id == gh_org["id"]
        ).first()

        if not org:
            org = Organization(
                id=uuid4(),
                github_org_id=gh_org["id"],
                github_org_slug=gh_org["login"],
                github_org_name=gh_org.get("description") or gh_org["login"],
                billing_email=user.email,
            )
            db.add(org)
            db.flush()

        # Create membership if not exists
        membership = db.query(OrgMembership).filter(
            OrgMembership.user_id == user.id,
            OrgMembership.org_id == org.id,
        ).first()

        if not membership:
            # Check user's role in the GitHub org
            user_role = await _get_github_org_role(
                access_token, gh_org["login"], github_user["login"]
            )
            membership = OrgMembership(
                user_id=user.id,
                org_id=org.id,
                role=user_role,
            )
            db.add(membership)

    db.commit()

    # Generate JWT token
    token_payload = {
        "user_id": str(user.id),
        "email": user.email,
        "github_login": user.github_login,
        "github_id": user.github_id,
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")

    # Redirect to frontend with token
    # Use fragment (#) for better security (token not sent to server in subsequent requests)
    return RedirectResponse(
        url=f"{redirect_uri}/auth/callback#token={token}"
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user info with organizations."""
    user = db.query(User).filter(
        User.id == current_user.user_id,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's organizations with roles
    memberships = db.query(OrgMembership, Organization).join(
        Organization, OrgMembership.org_id == Organization.id
    ).filter(
        OrgMembership.user_id == user.id,
    ).all()

    organizations = [
        OrganizationResponse(
            id=str(org.id),
            github_org_slug=org.github_org_slug,
            github_org_name=org.github_org_name,
            role=membership.role,
        )
        for membership, org in memberships
    ]

    return MeResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            github_login=user.github_login,
            github_id=user.github_id,
            github_avatar_url=user.github_avatar_url,
            created_at=user.created_at,
        ),
        organizations=organizations,
    )


@router.post("/logout")
async def logout():
    """
    Logout user.

    Note: JWT tokens are stateless, so logout is handled client-side
    by removing the token. This endpoint exists for API consistency.
    """
    return {"message": "Logout successful"}


@router.post("/refresh")
async def refresh_token(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Refresh JWT token.

    Returns a new token with extended expiration.
    """
    api_secrets = get_api_secrets()
    jwt_secret = api_secrets.get("jwt_secret", "changeme")

    # Generate new token
    token_payload = {
        "user_id": str(current_user.user_id),
        "email": current_user.email,
        "github_login": current_user.github_login,
        "github_id": current_user.github_id,
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")

    return {"token": token}

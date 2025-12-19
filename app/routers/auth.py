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

from app.database import get_db
from app.config import settings, get_github_secrets, get_api_secrets
from app.models.user import User
from app.models.organization import Organization
from app.models.org_membership import OrgMembership

router = APIRouter()

# In-memory state storage (use Redis in production)
_oauth_states: dict = {}


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
    # Validate state
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state token")

    state_data = _oauth_states.pop(state)
    redirect_uri = state_data["redirect_uri"]

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
            raise HTTPException(status_code=400, detail="No access token received")

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

    if not user:
        user = User(
            id=uuid4(),
            email=github_user.get("email") or f"{github_user['login']}@github.cicosts.dev",
            github_id=github_user["id"],
            github_login=github_user["login"],
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
            membership = OrgMembership(
                user_id=user.id,
                org_id=org.id,
                role="owner",  # First user is owner
            )
            db.add(membership)

    db.commit()

    # Generate JWT token
    token_payload = {
        "user_id": str(user.id),
        "email": user.email,
        "github_login": user.github_login,
        "exp": datetime.utcnow() + timedelta(days=7),
    }

    token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")

    # Redirect to frontend with token
    return RedirectResponse(
        url=f"{redirect_uri}?token={token}"
    )


@router.get("/me")
async def get_current_user(
    # TODO: Add JWT validation dependency
    db: Session = Depends(get_db),
):
    """Get current user info."""
    # Placeholder - will implement JWT validation
    return {"message": "Implement JWT validation"}


@router.post("/logout")
async def logout():
    """Logout user (client-side token removal)."""
    return {"message": "Logout successful"}

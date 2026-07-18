"""Minimal JWT auth + RBAC for the SitePulse prototype."""
from __future__ import annotations

import datetime as dt
import os

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import db

JWT_SECRET = os.environ.get("SITEPULSE_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 12

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user: db.User) -> str:
    payload = {
        "sub": user.id,
        "org_id": user.org_id,
        "site_id": user.site_id,
        "role": user.role,
        "exp": dt.datetime.utcnow() + dt.timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_db():
    yield from db.get_session()


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_db),
) -> db.User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = session.get(db.User, payload["sub"])
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def require_role(*roles: str):
    def _check(user: db.User = Depends(current_user)) -> db.User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user
    return _check


def assert_site_access(user: db.User, site: db.Site):
    """RBAC: user must belong to the site's org; non-admins are scoped to their assigned site."""
    if site.org_id != user.org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Site does not belong to your organization")
    if user.role != "admin" and user.site_id and user.site_id != site.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not assigned to this site")

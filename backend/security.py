# -*- coding: utf-8 -*-
"""Authentication, role based access control, audit logging and field level
encryption of channel credentials at rest."""
import base64
import datetime as dt
import hashlib
import hmac
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request

import config
from db import SessionLocal, User, Session as DbSession, AuditLog, Setting, utcnow

PBKDF2_ROUNDS = 240_000


# --------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}" \
           f"${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, dk_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# -------------------------------------------------- encryption at rest
def _fernet() -> Fernet:
    """Key resolution order: environment, then a generated key persisted in
    the settings table. In production this belongs in a managed secrets
    store, which is what Section 8.4 of the proposal commits to."""
    key = config.SECRET_KEY
    if not key:
        with SessionLocal() as s:
            row = s.get(Setting, "fernet_key")
            if row is None:
                key = Fernet.generate_key().decode()
                s.add(Setting(key="fernet_key", value=key))
                s.commit()
            else:
                key = row.value
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ""


def mask(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


# ----------------------------------------------------------------- sessions
def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    with SessionLocal() as s:
        s.add(DbSession(
            token=token, user_id=user.id,
            expires_at=utcnow() + dt.timedelta(hours=config.SESSION_TTL_HOURS)))
        u = s.get(User, user.id)
        u.last_login = utcnow()
        s.commit()
    return token


def destroy_session(token: str):
    with SessionLocal() as s:
        row = s.get(DbSession, token)
        if row:
            s.delete(row)
            s.commit()


def _token_from(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get("wdap_session", "")


def current_user(request: Request) -> User | None:
    token = _token_from(request)
    if not token:
        return None
    with SessionLocal() as s:
        row = s.get(DbSession, token)
        if row is None:
            return None
        if row.expires_at < utcnow():
            s.delete(row)
            s.commit()
            return None
        user = s.get(User, row.user_id)
        if user is None or not user.active:
            return None
        s.expunge(user)
        return user


def require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require(request: Request, permission: str) -> User:
    """Enforce a named permission from the matrix in config.PERMISSIONS."""
    user = require_user(request)
    allowed = config.PERMISSIONS.get(user.role, set())
    if permission not in allowed:
        audit(user, "access.denied", "permission", permission,
              f"role {user.role} lacks {permission}", request)
        raise HTTPException(
            status_code=403,
            detail=f"Role {user.role} is not permitted to {permission}")
    return user


# -------------------------------------------------------------------- audit
def audit(user, action: str, entity: str = "", entity_id: str = "",
          detail: str = "", request: Request | None = None):
    ip = ""
    if request is not None and request.client:
        ip = request.client.host or ""
    with SessionLocal() as s:
        s.add(AuditLog(
            user_id=getattr(user, "id", None),
            actor=getattr(user, "email", "system"),
            action=action, entity=entity, entity_id=str(entity_id),
            detail=detail, ip=ip))
        s.commit()


def hash_visitor(ip: str, ua: str) -> str:
    """Unique click counting without storing an identifiable address."""
    return hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:32]

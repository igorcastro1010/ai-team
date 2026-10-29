import hashlib
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import AuthSession, Event, LoginThrottle, Owner

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
COOKIE_NAME = "ai_team_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_owner(db: Session, username: str, password: str) -> None:
    username = username.strip()
    if not 2 <= len(username) <= 80 or len(password) < 12 or len(password) > 256:
        raise ValueError("Usuário deve ter 2–80 caracteres e senha 12–256 caracteres")
    if db.scalar(select(Owner)):
        raise ValueError("Proprietário já cadastrado; registro público desativado")
    db.add(Owner(id=1, username=username, password_hash=hasher.hash(password)))
    throttle_key = digest("owner-login")
    if db.get(LoginThrottle, throttle_key) is None:
        db.add(LoginThrottle(key=throttle_key, attempts=0, reset_at=int(time.time()) + 900))
    db.commit()


def authenticate(db: Session, username: str, password: str) -> str:
    now = int(time.time())
    # One private owner: a global persisted bucket also prevents username/IP rotation bypass.
    key = digest("owner-login")
    bucket = db.get(LoginThrottle, key)
    if not bucket:
        bucket = LoginThrottle(key=key, attempts=0, reset_at=now + 900)
        db.add(bucket)
        db.commit()
    db.execute(
        update(LoginThrottle)
        .where(LoginThrottle.key == key, LoginThrottle.reset_at <= now)
        .values(attempts=0, reset_at=now + 900)
    )
    reserved = db.execute(
        update(LoginThrottle)
        .where(
            LoginThrottle.key == key,
            LoginThrottle.attempts < 5,
            LoginThrottle.reset_at > now,
        )
        .values(attempts=LoginThrottle.attempts + 1)
    )
    db.commit()  # Atomic reservation across processes, before the expensive password check.
    if reserved.rowcount != 1:
        db.refresh(bucket)
        raise HTTPException(
            429,
            "Muitas tentativas. Aguarde 15 minutos.",
            headers={"Retry-After": str(max(1, bucket.reset_at - now))},
        )
    owner = db.scalar(select(Owner).where(Owner.username == username.strip()))
    try:
        hasher.verify(owner.password_hash if owner else dummy_hash, password)
    except VerificationError:
        raise HTTPException(401, "Usuário ou senha inválidos") from None
    if owner is None:
        raise HTTPException(401, "Usuário ou senha inválidos")
    db.execute(update(LoginThrottle).where(LoginThrottle.key == key).values(attempts=0))
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            token_hash=digest(token), owner_id=owner.id, expires_at=now + db.info["session_ttl"]
        )
    )
    db.add(Event(kind="auth.login", summary="Sessão iniciada", actor=owner.username))
    db.commit()
    return token


def require_owner(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) > 200:
        raise HTTPException(401, "Entre para acessar seu workspace")
    with request.app.state.database.session() as db:
        session = db.get(AuthSession, digest(token))
        if not session or session.expires_at <= int(time.time()):
            raise HTTPException(401, "Sessão expirada. Entre novamente.")
        owner = db.get(Owner, session.owner_id)
        if not owner:
            raise HTTPException(401, "Sessão inválida")
        return owner.username

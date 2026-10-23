from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password, verify_password, make_token, COOKIE_NAME, get_db, current_user, get_claims, guard_write, guard_origin
from app.core.validation import Registration, Login
from app.db.models import User
import os
from app.core.cache import allow_attempt

router = APIRouter()


def user_payload(user):
    return {"id": user.id, "name": user.name, "email": user.email}


def set_cookie(request: Request, response: Response, token: str):
    response.set_cookie(COOKIE_NAME, token, max_age=7*24*3600, httponly=True, secure=request.url.scheme == "https" or os.getenv("COOKIE_SECURE") == "true", samesite="lax", path="/")


@router.post("/register", status_code=201)
def register(payload: Registration, request: Request, response: Response, db: Session = Depends(get_db)):
    guard_origin(request)
    if not allow_attempt(request.client.host if request.client else "unknown", "register", 5, 600):
        raise HTTPException(429,"Too many registration attempts; try again later")
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "Email is already registered")
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email is already registered") from None
    db.refresh(user)
    token, csrf = make_token(user.id)
    set_cookie(request, response, token)
    return {"user": user_payload(user), "csrf_token": csrf}


@router.post("/login")
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    guard_origin(request)
    if not allow_attempt(request.client.host if request.client else "unknown", "login", 15, 300):
        raise HTTPException(429,"Too many sign-in attempts; try again later")
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    token, csrf = make_token(user.id)
    set_cookie(request, response, token)
    return {"user": user_payload(user), "csrf_token": csrf}


@router.get("/me")
def me(request: Request, user: User = Depends(current_user)):
    claims, _, _ = get_claims(request)
    return {"user": user_payload(user), "csrf_token": claims["csrf"]}


@router.post("/logout")
def logout(request: Request, response: Response, user: User = Depends(current_user)):
    guard_write(request)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"message": "Signed out"}

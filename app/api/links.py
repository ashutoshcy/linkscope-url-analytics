import io
import secrets
import string
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from fastapi.responses import RedirectResponse, StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, update
from sqlalchemy.exc import IntegrityError
import qrcode
from app.core.config import public_base_url
from app.core.validation import LinkCreate, LinkPatch
from app.core.security import get_db, current_user, guard_write
from app.core.analytics import classify, referrer_domain, fingerprint
from app.db.models import User, Link, Click, utcnow
from app.core.cache import get_link as get_cached_link, cache_link, invalidate_link, allow_attempt

router = APIRouter()
ALPHABET = string.ascii_letters + string.digits


def link_dict(link: Link, request: Request):
    base = public_base_url() or str(request.base_url).rstrip("/")
    return {"id":link.id,"slug":link.slug,"short_url":f"{base}/r/{link.slug}","target_url":link.target_url,"title":link.title,
            "description":link.description,"tags":link.tags,"is_active":link.is_active,
            "expires_at":link.expires_at.isoformat()+"Z" if link.expires_at else None,
            "created_at":link.created_at.isoformat()+"Z","updated_at":link.updated_at.isoformat()+"Z",
            "click_count":link.click_count,"status": "expired" if link.expires_at and link.expires_at <= utcnow() else "active" if link.is_active else "paused"}


def owned(db: Session, user: User, link_id: int) -> Link:
    link = db.scalar(select(Link).where(Link.id == link_id, Link.owner_id == user.id))
    if not link: raise HTTPException(404, "Link not found")
    return link


@router.get("")
def list_links(request: Request, q: str = Query("", max_length=120), status: Literal["all","active","paused","expired"] = "all", sort: Literal["recent","popular","oldest","title"] = "recent", limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Link).where(Link.owner_id == user.id)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(Link.title.ilike(term),Link.slug.ilike(term),Link.target_url.ilike(term),Link.tags.ilike(term)))
    if status == "active": query = query.where(Link.is_active.is_(True), or_(Link.expires_at.is_(None), Link.expires_at > utcnow()))
    if status == "paused": query = query.where(Link.is_active.is_(False))
    if status == "expired": query = query.where(Link.expires_at.is_not(None), Link.expires_at <= utcnow())
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = {"recent":Link.created_at.desc(),"popular":Link.click_count.desc(),"oldest":Link.created_at.asc(),"title":Link.title.asc()}[sort]
    links = db.scalars(query.order_by(order, Link.id.desc()).offset(offset).limit(limit)).all()
    return {"items":[link_dict(l,request) for l in links],"total":total,"limit":limit,"offset":offset}


@router.post("", status_code=201)
def create_link(payload: LinkCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    guard_write(request)
    if not allow_attempt(str(user.id), "create-link", 60, 3600):
        raise HTTPException(429, "Too many links created; try again later")
    for _ in range(8):
        slug = payload.slug or "".join(secrets.choice(ALPHABET) for _ in range(7))
        link = Link(owner_id=user.id, slug=slug, target_url=payload.target_url, title=payload.title, description=payload.description.strip(), tags=payload.tags.strip(), expires_at=payload.expires_at)
        db.add(link)
        try:
            db.commit()
            db.refresh(link)
            return link_dict(link, request)
        except IntegrityError:
            db.rollback()
            if payload.slug: raise HTTPException(409, "This custom alias is already taken") from None
    raise HTTPException(503, "Could not generate a unique link. Try again")


@router.get("/{link_id}")
def get_link(link_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return link_dict(owned(db, user, link_id), request)


@router.patch("/{link_id}")
def update_link(link_id: int, payload: LinkPatch, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    guard_write(request)
    link = owned(db, user, link_id)
    update = payload.model_dump(exclude_unset=True)
    for k,v in update.items():
        if k in ("target_url", "title") and v is None: raise HTTPException(422, f"{k} cannot be null")
        if k in ("description","tags") and v is None: v = ""
        setattr(link, k, v)
    link.updated_at = utcnow()
    db.commit()
    invalidate_link(link.slug)
    return link_dict(link, request)


@router.delete("/{link_id}", status_code=204)
def delete_link(link_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    guard_write(request)
    link = owned(db, user, link_id)
    db.delete(link)
    db.commit()
    invalidate_link(link.slug)
    return Response(status_code=204)


@router.get("/{link_id}/qr")
def qr_code(link_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = owned(db, user, link_id)
    qr = qrcode.QRCode(version=None, box_size=9, border=3, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(link_dict(link, request)["short_url"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="#171a36", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png", headers={"Cache-Control":"private, max-age=300"})


def redirect_link(slug: str, request: Request, session_factory):
    with session_factory() as db:
        cached = get_cached_link(slug)
        if cached:
            link_id = cached["id"]
            target = cached["target"]
            active = cached["active"]
            expires_at = datetime.fromisoformat(cached["expires_at"]) if cached["expires_at"] else None
        else:
            link = db.scalar(select(Link).where(Link.slug == slug))
            if link is None:
                return HTMLResponse('<h1>Link not found</h1><p>This short link does not exist.</p>', status_code=404)
            link_id = link.id
            target = link.target_url
            active = link.is_active
            expires_at = link.expires_at
            cache_link(slug, {"id":link.id,"target":link.target_url,"active":link.is_active,"expires_at":link.expires_at.isoformat() if link.expires_at else None})
        if not active or (expires_at and expires_at <= utcnow()):
            return HTMLResponse('<h1>Link unavailable</h1><p>This link is paused or has expired.</p>', status_code=410)
        ua = request.headers.get("user-agent", "")
        device, browser, platform, bot = classify(ua)
        now = utcnow()
        visitor_hash = fingerprint(request.client.host if request.client else "unknown", ua, link_id, now.date().isoformat())
        unique = not db.scalar(select(Click.id).where(Click.link_id == link_id, Click.fingerprint == visitor_hash, Click.is_bot.is_(False)).limit(1))
        params = request.query_params
        click = Click(link_id=link_id, clicked_at=now, fingerprint=visitor_hash, is_unique=unique and not bot, is_bot=bot,
          referrer=referrer_domain(request.headers.get("referer", "")), device=device,browser=browser,platform=platform,
          utm_source=params.get("utm_source", "")[:100], utm_medium=params.get("utm_medium", "")[:100],utm_campaign=params.get("utm_campaign", "")[:100])
        db.add(click)
        # Atomic increment avoids lost counters under concurrent redirects.
        if not bot: db.execute(update(Link).where(Link.id==link_id).values(click_count=Link.click_count+1))
        db.commit()
        return RedirectResponse(target, status_code=302, headers={"Cache-Control":"no-store, private","Referrer-Policy":"strict-origin-when-cross-origin"})

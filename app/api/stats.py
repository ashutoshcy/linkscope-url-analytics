import csv
import io
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.security import get_db, current_user
from app.db.models import User, Link, Click, utcnow
from app.core.analytics import rollup

router = APIRouter()


def spreadsheet_safe(value):
    # Prevent spreadsheet applications from interpreting untrusted cells as formulas.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def scoped_clicks(db: Session, user_id: int, days: int, link_id: int | None = None):
    cutoff = utcnow() - timedelta(days=days-1)
    cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    query = select(Click).join(Link).where(Link.owner_id == user_id, Click.clicked_at >= cutoff, Click.is_bot.is_(False))
    if link_id is not None: query = query.where(Link.id == link_id)
    return db.scalars(query.order_by(Click.clicked_at)).all()


@router.get("/overview")
def overview(request: Request, days: int = Query(14, ge=7, le=90), db: Session = Depends(get_db), user: User = Depends(current_user)):
    links = db.scalars(select(Link).where(Link.owner_id == user.id)).all()
    clicks = scoped_clicks(db,user.id,days)
    stat = rollup(clicks,days)
    stat.update({"total_links":len(links), "active_links":sum(1 for l in links if l.is_active and (not l.expires_at or l.expires_at > utcnow())),
                 "all_time_clicks":sum(l.click_count for l in links),
                 "top_links":[{"id":l.id,"title":l.title,"slug":l.slug,"clicks":l.click_count} for l in sorted(links,key=lambda x:x.click_count,reverse=True)[:5]]})
    return stat


@router.get("/links/{link_id}")
def detail(link_id: int, days: int = Query(30, ge=7, le=90), db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = db.scalar(select(Link).where(Link.id==link_id, Link.owner_id==user.id))
    if not link: raise HTTPException(404,"Link not found")
    result = rollup(scoped_clicks(db,user.id,days,link_id), days)
    result.update({"all_time_clicks":link.click_count, "link_id":link_id})
    return result


@router.get("/export.csv")
def export_csv(days: int = Query(30, ge=7, le=90), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows=scoped_clicks(db,user.id,days)
    link_ids={c.link_id for c in rows}
    links={l.id:l for l in db.scalars(select(Link).where(Link.owner_id==user.id, Link.id.in_(link_ids))).all()} if link_ids else {}
    buffer=io.StringIO()
    writer=csv.writer(buffer)
    writer.writerow(["timestamp_utc","short_alias","link_title","referrer","device","browser","platform","unique_visit","utm_source","utm_medium","utm_campaign"])
    for c in rows:
        l=links[c.link_id]
        writer.writerow([spreadsheet_safe(v) for v in [c.clicked_at.isoformat()+"Z",l.slug,l.title,c.referrer,c.device,c.browser,c.platform,c.is_unique,c.utm_source,c.utm_medium,c.utm_campaign]])
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition":f'attachment; filename="linkscope-analytics-{days}days.csv"',"Cache-Control":"private, no-store"})

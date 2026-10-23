"""Populate a local demo account. Never use in a public production deployment."""
import random
from datetime import timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import database_url
from app.core.security import hash_password
from app.db.models import Base, User, Link, Click, utcnow


def run():
    engine=create_engine(database_url())
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user=db.scalar(select(User).where(User.email=="demo@linkscope.dev"))
        if user:
            print("Demo account already exists. No data changed.")
            return
        user=User(name="Alex Morgan",email="demo@linkscope.dev",password_hash=hash_password("DemoPass123!"))
        db.add(user)
        db.flush()
        catalog=[
            ("summer-launch","Summer campaign launch","https://example.com/summer-collection","Marketing","Campaign"),
            ("product-tour","Interactive product tour","https://example.com/product/tour","Product","Product"),
            ("newsletter","Weekly insights newsletter","https://example.com/newsletter","Content","Newsletter"),
            ("design-system","Design system resources","https://example.com/resources/design-system","Design","Resources"),
            ("roadmap-2026","Public product roadmap","https://example.com/roadmap","Product","Updates"),
            ("event-tickets","Community meetup tickets","https://example.com/events","Events","Community"),
        ]
        random.seed(17)
        now=utcnow()
        for index,(slug,title,url,desc,tag) in enumerate(catalog):
            link=Link(owner_id=user.id,slug=slug,title=title,target_url=url,description=desc,tags=tag,created_at=now-timedelta(days=35-index*3),updated_at=now,click_count=0)
            db.add(link)
            db.flush()
            count=[131,94,68,48,30,19][index]
            for j in range(count):
                dt=now-timedelta(days=random.randrange(0,30),hours=random.randrange(0,24),minutes=random.randrange(0,60))
                click=Click(link_id=link.id,clicked_at=dt,fingerprint=f"sample-{index}-{j//2}",is_unique=(j%2==0),is_bot=False,
                  referrer=random.choice(["Direct","google.com","linkedin.com","instagram.com","x.com"]),
                  device=random.choices(["Desktop","Mobile","Tablet"],[60,37,3])[0],browser=random.choice(["Chrome","Safari","Firefox","Edge"]),platform=random.choice(["macOS","Windows","Android","iOS"]),
                  utm_source="",utm_medium="",utm_campaign="summer-launch" if index==0 else "")
                db.add(click)
                link.click_count += 1
        db.commit()
    print("Local demo ready: demo@linkscope.dev / DemoPass123!")

if __name__ == "__main__": run()

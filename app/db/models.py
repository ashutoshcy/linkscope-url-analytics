from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(90), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    links: Mapped[list["Link"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(280), default="", nullable=False)
    tags: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner: Mapped[User] = relationship(back_populates="links")
    clicks: Mapped[list["Click"]] = relationship(back_populates="link", cascade="all, delete-orphan")


class Click(Base):
    __tablename__ = "clicks"
    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"), nullable=False, index=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referrer: Mapped[str] = mapped_column(String(200), default="Direct", nullable=False)
    device: Mapped[str] = mapped_column(String(30), default="Desktop", nullable=False)
    browser: Mapped[str] = mapped_column(String(40), default="Other", nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="Other", nullable=False)
    utm_source: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    utm_medium: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    utm_campaign: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    link: Mapped[Link] = relationship(back_populates="clicks")
    __table_args__ = (Index("ix_clicks_link_time", "link_id", "clicked_at"),)

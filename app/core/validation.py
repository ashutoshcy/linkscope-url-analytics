import re
import ipaddress
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, model_validator

SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{4,32}$")
RESERVED = {"api", "login", "signup", "admin", "static", "r", "docs", "health", "assets", "logout", "favicon"}


def validate_target(value: str) -> str:
    value = value.strip()
    if len(value) > 2048:
        raise ValueError("URL cannot exceed 2048 characters")
    try:
        p = urlsplit(value)
        host = p.hostname
        port = p.port
    except ValueError as exc:
        raise ValueError("Invalid URL") from exc
    if p.scheme.lower() not in ("https", "http") or not host or p.username or p.password:
        raise ValueError("Enter a valid HTTP or HTTPS URL without credentials")
    if any(ch.isspace() for ch in value) or port == 0:
        raise ValueError("URL cannot contain spaces or an invalid port")
    if host.lower() in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        raise ValueError("Local network URLs are not supported")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("Private network URLs are not supported")
    except ValueError as exc:
        if "Private network" in str(exc):
            raise
        if "." not in host:
            raise ValueError("Use a public hostname such as example.com") from exc
    return value


class Registration(BaseModel):
    name: str = Field(min_length=2, max_length=90)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if len(value)<2: raise ValueError("Name must be at least 2 characters")
        return value


class Login(BaseModel):
    email: str
    password: str


class LinkCreate(BaseModel):
    target_url: str
    title: str = Field(min_length=1, max_length=120)
    slug: str | None = None
    description: str = Field(default="", max_length=280)
    tags: str = Field(default="", max_length=240)
    expires_at: datetime | None = None

    @field_validator("target_url")
    @classmethod
    def valid_url(cls, v):
        return validate_target(v)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v):
        v = v.strip()
        if not v: raise ValueError("Title cannot be empty")
        return v

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, v):
        if v is not None and (not SLUG_PATTERN.fullmatch(v) or v.lower() in RESERVED):
            raise ValueError("Slug must be 4–32 letters, numbers, hyphens, or underscores")
        return v

    @field_validator("expires_at")
    @classmethod
    def future(cls, v):
        if v is not None:
            if v.tzinfo is not None:
                v = v.astimezone(timezone.utc).replace(tzinfo=None)
            if v <= datetime.now(timezone.utc).replace(tzinfo=None):
                raise ValueError("Expiration must be in the future")
        return v


class LinkPatch(BaseModel):
    target_url: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=280)
    tags: str | None = Field(default=None, max_length=240)
    is_active: bool | None = None
    expires_at: datetime | None = None

    @field_validator("target_url")
    @classmethod
    def valid_url(cls, v):
        return validate_target(v) if v is not None else None

    @field_validator("title")
    @classmethod
    def valid_title(cls, v):
        if v is not None and not v.strip(): raise ValueError("Title cannot be empty")
        return v.strip() if v is not None else None

    @field_validator("expires_at")
    @classmethod
    def future(cls, v):
        return LinkCreate.future(v)

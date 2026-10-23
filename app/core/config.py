import os


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./linkscope.db")


def secret_key() -> str:
    key = os.getenv("SECRET_KEY", "dev-only-insecure-replace-before-deployment")
    if os.getenv("APP_ENV", "development") == "production" and (key == "dev-only-insecure-replace-before-deployment" or len(key) < 32):
        raise RuntimeError("Set a unique SECRET_KEY of at least 32 characters for production")
    return key


def public_base_url() -> str | None:
    url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    return url or None

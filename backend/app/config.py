from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./points.db"
    secret_key: str = "dev-secret-change-me-dev-secret-change-me"
    access_token_expire_minutes: int = 480
    first_admin_username: str = "admin"
    first_admin_password: str = "admin12345"
    first_admin_email: str = "admin@example.local"
    cookie_secure: bool = False

    class Config:
        env_file = ".env"

settings = Settings()

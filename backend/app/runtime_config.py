import json
import os
from pathlib import Path
from urllib.parse import quote_plus

DEFAULT_CONFIG_PATH = "/data/config.json"


def config_path() -> Path:
    return Path(os.getenv("APP_CONFIG_PATH", DEFAULT_CONFIG_PATH))


def _env_database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


def is_installed() -> bool:
    return bool(_env_database_url()) or config_path().exists()


def load_config() -> dict:
    if config_path().exists():
        return json.loads(config_path().read_text())
    if _env_database_url():
        return {"database_url": _env_database_url(), "database": {"driver": "env", "host": "env"}}
    return {}


def _normalise_database(database: dict) -> dict:
    return {
        "driver": database.get("driver") or "mysql+pymysql",
        "host": database["host"],
        "port": int(database.get("port") or 3306),
        "database": database["database"],
        "username": database["username"],
        "password": database.get("password", ""),
    }


def _write_config(cfg: dict) -> dict:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))
    os.chmod(path, 0o600)
    return cfg


def save_install_config(database: dict) -> dict:
    cfg = load_config()
    cfg["database"] = _normalise_database(database)
    return _write_config(cfg)


def access_settings() -> dict:
    cfg = load_config()
    access = cfg.get("access") or {}
    return {
        "local_only_enabled": bool(access.get("local_only_enabled", False)),
        "block_ans_network_enabled": bool(access.get("block_ans_network_enabled", True)),
    }


def save_access_settings(access: dict) -> dict:
    current = access_settings()
    current.update({k: bool(v) for k, v in access.items() if k in current})
    cfg = load_config()
    cfg["access"] = current
    _write_config(cfg)
    return current


def database_url() -> str | None:
    env_url = _env_database_url()
    if env_url:
        return env_url
    cfg = load_config()
    if "database_url" in cfg:
        return cfg["database_url"]
    db = cfg.get("database")
    if not db:
        return None
    driver = db.get("driver") or "mysql+pymysql"
    user = quote_plus(db.get("username", ""))
    password = quote_plus(db.get("password", ""))
    host = db.get("host", "localhost")
    port = int(db.get("port") or 3306)
    name = db.get("database", "pointsdb")
    return f"{driver}://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


def install_status() -> dict:
    cfg = load_config()
    db = cfg.get("database") or {}
    public_db = {k: v for k, v in db.items() if k != "password"}
    return {
        "installed": is_installed(),
        "database_configured": bool(database_url()),
        "database": public_db or None,
    }

import importlib
import json


def test_install_status_reports_uninstalled_when_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_CONFIG_PATH", str(tmp_path / "app-config.json"))
    import app.runtime_config as runtime_config
    importlib.reload(runtime_config)

    assert runtime_config.is_installed() is False
    assert runtime_config.install_status()["installed"] is False
    assert runtime_config.install_status()["database_configured"] is False


def test_save_install_config_persists_mysql_connection_without_password(tmp_path, monkeypatch):
    config_path = tmp_path / "app-config.json"
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    import app.runtime_config as runtime_config
    importlib.reload(runtime_config)

    runtime_config.save_install_config(
        database={
            "host": "mysql",
            "port": 3306,
            "database": "pointsdb",
            "username": "pointsapp",
            "password": "s3cr3t",
        }
    )

    assert runtime_config.is_installed() is True
    status = runtime_config.install_status()
    assert status["installed"] is True
    assert status["database_configured"] is True
    assert status["database"]["host"] == "mysql"
    assert "password" not in status["database"]

    saved = json.loads(config_path.read_text())
    assert saved["database"]["password"] == "s3cr3t"
    assert saved["database"]["driver"] == "mysql+pymysql"
    assert runtime_config.database_url().startswith("mysql+pymysql://pointsapp:s3cr3t@mysql:3306/pointsdb")

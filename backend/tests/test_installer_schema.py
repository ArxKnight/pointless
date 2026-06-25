import pytest
from pydantic import ValidationError

from app.schemas.api import InstallIn


def test_install_schema_requires_admin_for_fresh_database():
    with pytest.raises(ValidationError):
        InstallIn.model_validate(
            {
                "database": {
                    "host": "mysql",
                    "port": 3306,
                    "database": "pointsdb",
                    "username": "pointsapp",
                    "password": "pw123456",
                },
                "reuse_existing_database": False,
            }
        )


def test_install_schema_allows_reuse_existing_database_without_admin():
    payload = InstallIn.model_validate(
        {
            "database": {
                "host": "mysql",
                "port": 3306,
                "database": "pointsdb",
                "username": "pointsapp",
                "password": "pw123456",
            },
            "reuse_existing_database": True,
        }
    )

    assert payload.reuse_existing_database is True
    assert payload.admin is None

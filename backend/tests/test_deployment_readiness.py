"""Step 11 — deployment & production-readiness tests.

These cover the deployment guards added in Step 11 and the startup configuration
surface. They never touch the demo database, never call a network endpoint and
never assert on secret values (only that the guards refuse to proceed).
"""

import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.database.session import ensure_sqlite_database_directory
from app.main import create_app

#: The insecure placeholder defined in app/core/config.py.
DEV_PLACEHOLDER_SECRET = "dev-only-insecure-jwt-secret-CHANGE-ME-before-any-real-deployment"

STRONG_SECRET = "0123456789abcdef" * 4  # 64 chars, test value only.


def _production_settings(**overrides: object) -> Settings:
    """Production settings that bypass the local .env for every field given."""
    base: dict[str, object] = {
        "app_env": "production",
        "debug": False,
        "jwt_secret_key": STRONG_SECRET,
        "cors_origins": "https://geneverify.example.com",
        "ai_provider": "qwen",
        "qwen_api_key": "test-key-never-used",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


# --- production startup guards -------------------------------------------


def test_development_settings_use_the_insecure_placeholder():
    """Guard sanity check: the placeholder really is the development default."""
    assert Settings(_env_file=None).jwt_secret_key == DEV_PLACEHOLDER_SECRET
    assert Settings(_env_file=None, jwt_secret_key=DEV_PLACEHOLDER_SECRET).using_insecure_dev_jwt_secret


def test_production_refuses_the_insecure_development_jwt_secret():
    settings = _production_settings(jwt_secret_key=DEV_PLACEHOLDER_SECRET)
    with pytest.raises(RuntimeError) as excinfo:
        create_app(settings)
    message = str(excinfo.value)
    assert "JWT_SECRET_KEY" in message
    # The refusal must not echo any secret value.
    assert DEV_PLACEHOLDER_SECRET not in message
    assert "test-key" not in message


def test_production_refuses_debug_mode():
    settings = _production_settings(debug=True)
    with pytest.raises(RuntimeError) as excinfo:
        create_app(settings)
    assert "DEBUG" in str(excinfo.value)


def test_production_boots_with_a_strong_secret_and_debug_off():
    app = create_app(_production_settings())
    assert isinstance(app, FastAPI)
    assert app.debug is False


def test_staging_is_not_subject_to_the_production_guards():
    """Only APP_ENV=production hard-fails; staging keeps the dev behaviour."""
    settings = _production_settings(app_env="staging", debug=True, jwt_secret_key=DEV_PLACEHOLDER_SECRET)
    assert create_app(settings) is not None


def test_ai_provider_must_be_qwen_or_mock():
    with pytest.raises(ValueError, match="AI_PROVIDER"):
        _production_settings(ai_provider="chatgpt")


def test_invalid_environment_name_is_refused():
    with pytest.raises(ValueError, match="APP_ENV"):
        _production_settings(app_env="prod")


# --- database deployment readiness ---------------------------------------


def test_sqlite_parent_directory_is_created(tmp_path: Path):
    target = tmp_path / "nested" / "deeper" / "geneverify.db"
    assert not target.parent.exists()

    created = ensure_sqlite_database_directory(f"sqlite:///{target.as_posix()}")

    assert created == target.parent.resolve()
    assert target.parent.is_dir()
    # The database file itself is still untouched (SQLite creates it lazily).
    assert not target.exists()


def test_relative_sqlite_url_resolves_to_the_working_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ensure_sqlite_database_directory("sqlite:///./geneverify.db") == tmp_path.resolve()


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:", "sqlite+aiosqlite://"])
def test_in_memory_and_non_sqlite_urls_need_no_directory(url: str):
    assert ensure_sqlite_database_directory(url) is None


def test_postgres_url_is_left_alone(tmp_path: Path):
    """A managed-database URL must not create local directories."""
    before = set(tmp_path.iterdir())
    assert ensure_sqlite_database_directory(
        "postgresql+psycopg://user:pass@db.example:5432/geneverify"
    ) is None
    assert set(tmp_path.iterdir()) == before


# --- CORS / storage configuration surface ---------------------------------


def test_cors_origins_are_configurable_and_split():
    settings = _production_settings(
        cors_origins="https://a.example, https://b.example ,https://c.example"
    )
    assert settings.cors_origin_list == ["https://a.example", "https://b.example", "https://c.example"]


def test_document_storage_path_and_size_limit_are_configurable():
    settings = _production_settings(document_storage_path="/srv/data/documents", max_document_size_mb=25)
    assert settings.document_storage_path == "/srv/data/documents"
    assert settings.max_document_size_mb == 25


def test_document_storage_size_limit_is_bounded():
    with pytest.raises(ValueError):
        _production_settings(max_document_size_mb=5_000)


# --- startup command surface (run.py) -------------------------------------


@pytest.fixture()
def run_module():
    """Import backend/run.py (the deployment startup wrapper)."""
    return importlib.import_module("run")


def test_run_py_defaults_to_port_8000(run_module, monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert run_module._port() == 8000


def test_run_py_honours_the_platform_port(run_module, monkeypatch):
    monkeypatch.setenv("PORT", "12345")
    assert run_module._port() == 12345


@pytest.mark.parametrize("value", ["", "   "])
def test_run_py_treats_an_empty_port_as_unset(run_module, monkeypatch, value):
    monkeypatch.setenv("PORT", value)
    assert run_module._port() == 8000


@pytest.mark.parametrize("value", ["http://8080", "80 80"])
def test_run_py_refuses_a_non_numeric_port(run_module, monkeypatch, value):
    monkeypatch.setenv("PORT", value)
    with pytest.raises(RuntimeError, match="PORT must be a number"):
        run_module._port()


@pytest.mark.parametrize("value", ["0", "70000", "-1"])
def test_run_py_refuses_an_out_of_range_port(run_module, monkeypatch, value):
    monkeypatch.setenv("PORT", value)
    with pytest.raises(RuntimeError, match="between 1 and 65535"):
        run_module._port()


def test_run_py_selects_production_host(run_module, monkeypatch):
    """Production binds all interfaces; development stays on loopback."""
    captured: dict[str, object] = {}

    def fake_run(import_string: str, **kwargs: object) -> None:
        captured["import_string"] = import_string
        captured.update(kwargs)

    monkeypatch.setattr(run_module.uvicorn, "run", fake_run)
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setattr(
        run_module,
        "get_settings",
        lambda: _production_settings(log_level="INFO"),
    )

    run_module.main()

    assert captured["import_string"] == "app.main:app"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9000


def test_run_py_development_host_is_loopback(run_module, monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        run_module.uvicorn,
        "run",
        lambda import_string, **kwargs: captured.update(kwargs),
    )
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(
        run_module,
        "get_settings",
        lambda: Settings(_env_file=None, app_env="development"),
    )

    run_module.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8000


def test_explicit_host_env_wins(run_module, monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        run_module.uvicorn,
        "run",
        lambda import_string, **kwargs: captured.update(kwargs),
    )
    monkeypatch.setenv("HOST", "172.17.0.5")
    monkeypatch.setattr(
        run_module,
        "get_settings",
        lambda: _production_settings(),
    )

    run_module.main()

    assert captured["host"] == "172.17.0.5"

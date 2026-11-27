import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.database as db
from backend.services.auth import create_token_pair, hash_password


@pytest.fixture
def refresh_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'refresh.db'}")
    db.Base.metadata.create_all(bind=engine)
    previous_engine = db.engine
    previous_session = db.SessionLocal
    db.engine = engine
    db.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield
    db.engine = previous_engine
    db.SessionLocal = previous_session
    engine.dispose()


@pytest.fixture
def refresh_user(refresh_db):
    email = f"refresh-{uuid.uuid4().hex}@example.com"
    return db.add_user(email, hash_password("RefreshTest123!"))


def test_refresh_token_almacenado_esta_activo(refresh_user):
    tokens = create_token_pair(refresh_user.id, refresh_user.email)
    db.store_refresh_token(
        refresh_user.id,
        tokens["jti"],
        tokens["refresh_expires_at"],
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert db.is_refresh_token_active(refresh_user.id, tokens["jti"])


def test_rotacion_revoca_anterior_y_activa_nueva(refresh_user):
    old_tokens = create_token_pair(refresh_user.id, refresh_user.email)
    db.store_refresh_token(refresh_user.id, old_tokens["jti"], old_tokens["refresh_expires_at"])

    new_tokens = create_token_pair(refresh_user.id, refresh_user.email)
    assert db.rotate_refresh_token(
        refresh_user.id,
        old_tokens["jti"],
        new_tokens["jti"],
        new_tokens["refresh_expires_at"],
    )

    assert not db.is_refresh_token_active(refresh_user.id, old_tokens["jti"])
    assert db.is_refresh_token_active(refresh_user.id, new_tokens["jti"])


def test_rotacion_rechaza_token_ya_revocado(refresh_user):
    tokens = create_token_pair(refresh_user.id, refresh_user.email)
    db.store_refresh_token(refresh_user.id, tokens["jti"], tokens["refresh_expires_at"])
    db.rotate_refresh_token(refresh_user.id, tokens["jti"], "nuevo", tokens["refresh_expires_at"])

    assert not db.rotate_refresh_token(
        refresh_user.id,
        tokens["jti"],
        "otro",
        tokens["refresh_expires_at"],
    )


def test_revocacion_explicita_invalida_token(refresh_user):
    tokens = create_token_pair(refresh_user.id, refresh_user.email)
    db.store_refresh_token(refresh_user.id, tokens["jti"], tokens["refresh_expires_at"])

    assert db.revoke_refresh_token(refresh_user.id, tokens["jti"])
    assert not db.is_refresh_token_active(refresh_user.id, tokens["jti"])

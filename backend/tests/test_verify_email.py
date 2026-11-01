"""Endpoint tests for the email confirmation link (/api/verify-email).

The link is opened from an email, so every outcome must redirect back to the
frontend's login page instead of returning a raw JSON error.
"""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from config import settings
from database import models
from database.database import get_session
from main import app
from services import auth_service


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


def _token(expire_hours=24):
    return auth_service.create_email_verification_token(
        email="alice@fh-swf.de", name="Alice", hashed_password="x", expire_hours=expire_hours
    )


def _redirect(response):
    assert response.status_code == 307
    location = urlparse(response.headers["location"])
    assert (
        f"{location.scheme}://{location.netloc}{location.path}" == f"{settings.FRONTEND_URL}/login"
    )
    return parse_qs(location.query)


def test_creates_the_user_and_redirects_to_login(client, db):
    query = _redirect(client.get("/api/verify-email", params={"token": _token()}))

    assert query == {"verified": ["true"]}
    assert db.exec(select(models.User).where(models.User.email == "alice@fh-swf.de")).one()


def test_second_click_still_redirects_to_login(client, db):
    # Mail scanners (e.g. Microsoft Safe Links) often open the link first.
    token = _token()
    client.get("/api/verify-email", params={"token": token})

    query = _redirect(client.get("/api/verify-email", params={"token": token}))

    assert query == {"verified": ["true"]}
    assert len(db.exec(select(models.User)).all()) == 1


def test_expired_link_redirects_with_the_error(client, db):
    query = _redirect(client.get("/api/verify-email", params={"token": _token(expire_hours=-1)}))

    assert "expired" in query["verify_error"][0]
    assert db.exec(select(models.User)).all() == []


def test_invalid_link_redirects_with_the_error(client):
    query = _redirect(client.get("/api/verify-email", params={"token": "garbage"}))

    assert query == {"verify_error": ["Invalid confirmation link."]}

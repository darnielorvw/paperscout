"""Endpoint tests for the reading list (/api/saved-articles).

They run against an in-memory SQLite database and a fixed logged-in user, by
overriding the session and auth dependencies. The app's lifespan (migrations,
scheduler) doesn't run, since the TestClient isn't used as a context manager.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database import models
from database.database import get_session
from main import app
from services import auth_service


def _article(article_id: str, **overrides):
    article = {
        "id": article_id,
        "title": f"Paper {article_id}",
        "journal_name": "Nature",
        "doi": f"https://doi.org/{article_id}",
        "library_url": f"https://library.example/openurl?rft_id=info:doi/{article_id}",
    }
    article.update(overrides)
    return article


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def users(db):
    alice = models.User(
        email="alice@example.org", name="Alice", hashed_password="x", institution=""
    )
    bob = models.User(email="bob@example.org", name="Bob", hashed_password="x", institution="")
    db.add_all([alice, bob])
    db.commit()
    return {"alice": alice, "bob": bob}


@pytest.fixture
def client(db, users):
    current = {"user": users["alice"]}
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[auth_service.get_current_user] = lambda: current["user"]
    client = TestClient(app)
    # Lets a test act as another user.
    client.login_as = lambda name: current.update(user=users[name])
    yield client
    app.dependency_overrides.clear()


def _save(client, *articles):
    return client.post("/api/saved-articles", json={"articles": list(articles)})


class TestSaveArticles:
    def test_saves_and_returns_the_entries(self, client):
        response = _save(client, _article("10.1/a"), _article("10.1/b"))

        assert response.status_code == 201
        body = response.json()
        assert body["skipped"] == 0
        assert [entry["article"]["id"] for entry in body["results"]] == ["10.1/a", "10.1/b"]
        entry = body["results"][0]
        assert entry["isRead"] is False
        assert entry["article"]["library_url"].endswith("10.1/a")

    def test_skips_articles_already_on_the_list(self, client):
        _save(client, _article("10.1/a"))

        body = _save(client, _article("10.1/a"), _article("10.1/b")).json()

        assert body["skipped"] == 1
        assert [entry["article"]["id"] for entry in body["results"]] == ["10.1/b"]

    def test_skips_duplicates_within_one_request(self, client):
        body = _save(client, _article("10.1/a"), _article("10.1/a")).json()

        assert body["skipped"] == 1
        assert len(body["results"]) == 1

    def test_empty_list_is_rejected(self, client):
        assert client.post("/api/saved-articles", json={"articles": []}).status_code == 422


class TestGetSavedArticles:
    def test_lists_only_the_own_entries(self, client):
        _save(client, _article("10.1/a"))
        client.login_as("bob")
        _save(client, _article("10.1/b"))

        results = client.get("/api/saved-articles").json()["results"]

        assert [entry["article"]["id"] for entry in results] == ["10.1/b"]

    def test_most_recently_saved_first(self, client):
        _save(client, _article("10.1/a"))
        _save(client, _article("10.1/b"))

        results = client.get("/api/saved-articles").json()["results"]

        assert [entry["article"]["id"] for entry in results] == ["10.1/b", "10.1/a"]


class TestUpdateSavedArticle:
    def test_marks_as_read_and_unread(self, client):
        saved_id = _save(client, _article("10.1/a")).json()["results"][0]["id"]

        response = client.patch(f"/api/saved-articles/{saved_id}", json={"isRead": True})
        assert response.status_code == 200
        assert response.json()["isRead"] is True

        response = client.patch(f"/api/saved-articles/{saved_id}", json={"isRead": False})
        assert response.json()["isRead"] is False

    def test_is_read_is_required(self, client):
        saved_id = _save(client, _article("10.1/a")).json()["results"][0]["id"]

        assert client.patch(f"/api/saved-articles/{saved_id}", json={}).status_code == 422

    def test_other_users_entry_is_not_found(self, client):
        saved_id = _save(client, _article("10.1/a")).json()["results"][0]["id"]
        client.login_as("bob")

        response = client.patch(f"/api/saved-articles/{saved_id}", json={"isRead": True})

        assert response.status_code == 404


class TestDeleteSavedArticle:
    def test_removes_the_entry(self, client):
        saved_id = _save(client, _article("10.1/a")).json()["results"][0]["id"]

        assert client.delete(f"/api/saved-articles/{saved_id}").status_code == 204
        assert client.get("/api/saved-articles").json()["results"] == []

    def test_other_users_entry_is_not_found(self, client):
        saved_id = _save(client, _article("10.1/a")).json()["results"][0]["id"]
        client.login_as("bob")

        assert client.delete(f"/api/saved-articles/{saved_id}").status_code == 404


class TestDeleteSavedArticles:
    def test_removes_only_the_given_entries(self, client):
        results = _save(client, _article("10.1/a"), _article("10.1/b"), _article("10.1/c"))
        ids = [entry["id"] for entry in results.json()["results"]]

        response = client.delete("/api/saved-articles", params={"ids": ids[:2]})

        assert response.status_code == 204
        remaining = client.get("/api/saved-articles").json()["results"]
        assert [entry["article"]["id"] for entry in remaining] == ["10.1/c"]

    def test_ignores_other_users_entries(self, client):
        saved_id = _save(client, _article("10.1/a")).json()["results"][0]["id"]
        client.login_as("bob")

        assert client.delete("/api/saved-articles", params={"ids": [saved_id]}).status_code == 204

        client.login_as("alice")
        assert len(client.get("/api/saved-articles").json()["results"]) == 1

    def test_ids_are_required(self, client):
        assert client.delete("/api/saved-articles").status_code == 422

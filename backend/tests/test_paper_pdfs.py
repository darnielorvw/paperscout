"""Endpoint tests for PDF requests on the reading list and the admin PDF upload.

Same setup as test_saved_articles.py: an in-memory SQLite database and a fixed
logged-in user. Mails are collected by a stub instead of being sent.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import main
from database import models
from database.database import get_session
from main import app
from services import auth_service, blob_service

PDF_URL = "https://abc123.public.blob.vercel-storage.com/papers/10.1_a-Xy7Rq.pdf"


def _article(article_id: str):
    return {
        "id": article_id,
        "title": f"Paper {article_id}",
        "journal_name": "Nature",
        "doi": f"https://doi.org/{article_id}",
    }


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
    admin = models.User(
        email="admin@example.org",
        name="Admin",
        hashed_password="x",
        institution="",
        is_admin=True,
    )
    db.add_all([alice, bob, admin])
    db.commit()
    return {"alice": alice, "bob": bob, "admin": admin}


@pytest.fixture
def mails(monkeypatch):
    sent = []

    async def send_email(to, subject, html_body):
        sent.append((to, subject))
        return True

    monkeypatch.setattr(main.mail_service, "send_email", send_email)
    return sent


@pytest.fixture
def client(db, users, mails):
    current = {"user": users["alice"]}
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[auth_service.get_current_user] = lambda: current["user"]
    client = TestClient(app)
    client.login_as = lambda name: current.update(user=users[name])
    yield client
    app.dependency_overrides.clear()


def _save(client, article_id="10.1/a"):
    response = client.post("/api/saved-articles", json={"articles": [_article(article_id)]})
    return response.json()["results"][0]


def _store_pdf(client, article_id="10.1/a", url=PDF_URL):
    client.login_as("admin")
    response = client.put("/api/admin/pdfs", json={"article_id": article_id, "url": url})
    client.login_as("alice")
    return response


class TestPdfRequest:
    def test_request_marks_entry_and_mails_admins(self, client, mails):
        entry = _save(client)
        assert entry["pdfRequested"] is False
        assert entry["pdfUrl"] is None

        response = client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        assert response.status_code == 200
        assert response.json()["pdfRequested"] is True
        assert mails == [("admin@example.org", "PDF request: Paper 10.1/a")]

    def test_second_request_does_not_mail_again(self, client, mails):
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        assert len(mails) == 1

    def test_shows_up_in_reading_list(self, client):
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        listed = client.get("/api/saved-articles").json()["results"][0]
        assert listed["pdfRequested"] is True

    def test_cancel(self, client):
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        response = client.delete(f"/api/saved-articles/{entry['id']}/pdf-request")

        assert response.json()["pdfRequested"] is False

    def test_removing_the_paper_removes_the_request(self, client, db):
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        client.delete(f"/api/saved-articles/{entry['id']}")

        assert db.exec(select(models.PaperRequest)).all() == []

    def test_bulk_removal_removes_the_requests(self, client, db):
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        client.delete(f"/api/saved-articles?ids={entry['id']}")

        assert db.exec(select(models.PaperRequest)).all() == []

    def test_no_request_once_a_pdf_is_there(self, client, db, mails):
        entry = _save(client)
        _store_pdf(client)

        response = client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        assert response.json()["pdfUrl"] == PDF_URL
        assert db.exec(select(models.PaperRequest)).all() == []
        assert mails == []

    def test_other_users_entry_is_not_found(self, client):
        entry = _save(client)
        client.login_as("bob")

        response = client.post(f"/api/saved-articles/{entry['id']}/pdf-request")

        assert response.status_code == 404


class TestAdminPdfRequests:
    def test_lists_requests_grouped_by_paper(self, client):
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")
        client.login_as("bob")
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")
        client.login_as("admin")

        body = client.get("/api/admin/pdf-requests").json()

        assert len(body["results"]) == 1
        paper = body["results"][0]
        assert paper["articleId"] == "10.1/a"
        assert paper["title"] == "Paper 10.1/a"
        assert paper["requesters"] == ["alice@example.org", "bob@example.org"]
        assert paper["pdfUrl"] is None

    def test_admin_only(self, client):
        assert client.get("/api/admin/pdf-requests").status_code == 403
        assert _store_pdf(client).status_code != 403
        client.login_as("alice")
        response = client.put("/api/admin/pdfs", json={"article_id": "10.1/a", "url": PDF_URL})
        assert response.status_code == 403


class TestStorePdf:
    def test_everyone_with_the_paper_sees_the_pdf(self, client):
        _save(client)
        client.login_as("bob")
        _save(client)  # Bob never asked for it.

        assert _store_pdf(client).status_code == 200

        client.login_as("bob")
        assert client.get("/api/saved-articles").json()["results"][0]["pdfUrl"] == PDF_URL

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.example/papers/10.1_a-Xy7Rq.pdf",
            "https://abc123.public.blob.vercel-storage.com/papers/10.1_b-Xy7Rq.pdf",
            "http://abc123.public.blob.vercel-storage.com/papers/10.1_a-Xy7Rq.pdf",
        ],
    )
    def test_rejects_foreign_urls(self, client, url):
        assert _store_pdf(client, url=url).status_code == 400

    def test_replacing_deletes_the_old_blob(self, client, monkeypatch):
        deleted = []

        async def delete_blob(url):
            deleted.append(url)

        monkeypatch.setattr(blob_service, "delete_blob", delete_blob)
        new_url = PDF_URL.replace("Xy7Rq", "Ab12C")
        _store_pdf(client)
        _store_pdf(client, url=new_url)

        assert deleted == [PDF_URL]


class TestDeletePdf:
    def test_deletes_pdf_and_blob_and_reopens_the_request(self, client, monkeypatch):
        deleted = []

        async def delete_blob(url):
            deleted.append(url)

        monkeypatch.setattr(blob_service, "delete_blob", delete_blob)
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")
        _store_pdf(client)
        client.login_as("admin")

        response = client.delete("/api/admin/pdfs", params={"article_id": "10.1/a"})

        assert response.status_code == 204
        assert deleted == [PDF_URL]
        paper = client.get("/api/admin/pdf-requests").json()["results"][0]
        assert paper["pdfUrl"] is None
        client.login_as("alice")
        listed = client.get("/api/saved-articles").json()["results"][0]
        assert listed["pdfUrl"] is None
        assert listed["pdfRequested"] is True

    def test_missing_pdf_is_404(self, client):
        client.login_as("admin")

        response = client.delete("/api/admin/pdfs", params={"article_id": "10.1/a"})

        assert response.status_code == 404

    def test_admin_only(self, client):
        response = client.delete("/api/admin/pdfs", params={"article_id": "10.1/a"})

        assert response.status_code == 403


class TestUploadToken:
    def test_unavailable_without_blob_store(self, client, monkeypatch):
        monkeypatch.setattr(main.settings, "BLOB_READ_WRITE_TOKEN", "")
        client.login_as("admin")

        response = client.post("/api/admin/pdf-upload-token", json={"article_id": "10.1/a"})

        assert response.status_code == 503

    def test_returns_token_for_the_papers_pathname(self, client, monkeypatch):
        monkeypatch.setattr(main.settings, "BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_Store1_secret")
        client.login_as("admin")

        body = client.post("/api/admin/pdf-upload-token", json={"article_id": "10.1/a"}).json()

        assert body["pathname"] == "papers/10.1_a.pdf"
        assert body["clientToken"].startswith("vercel_blob_client_Store1_")


class TestPdfsWithoutRequests:
    def test_listed_after_every_requester_removed_the_paper(self, client):
        entry = _save(client)
        client.post(f"/api/saved-articles/{entry['id']}/pdf-request")
        _store_pdf(client)
        client.delete(f"/api/saved-articles/{entry['id']}")
        client.login_as("admin")

        paper = client.get("/api/admin/pdf-requests").json()["results"][0]

        assert paper["articleId"] == "10.1/a"
        assert paper["pdfUrl"] == PDF_URL
        assert paper["requesters"] == []
        assert paper["requestedAt"] is None
        # Nobody has the paper anymore, so only the DOI is known.
        assert paper["title"] is None
        assert paper["doi"] == "https://doi.org/10.1/a"

    def test_details_come_from_any_saved_copy(self, client):
        _save(client)  # Alice keeps it without asking.
        _store_pdf(client)
        client.login_as("admin")

        paper = client.get("/api/admin/pdf-requests").json()["results"][0]

        assert paper["title"] == "Paper 10.1/a"
        assert paper["requesters"] == []

"""Unit tests for the password hashing helpers in user_service."""

from services import user_service


class TestPasswordHashing:
    def test_hash_is_not_the_plaintext(self):
        assert user_service.get_password_hash("s3cret!") != "s3cret!"

    def test_hashing_the_same_password_twice_gives_different_hashes(self):
        assert user_service.get_password_hash("s3cret!") != user_service.get_password_hash(
            "s3cret!"
        )

    def test_verify_accepts_the_correct_password(self):
        hashed = user_service.get_password_hash("s3cret!")
        assert user_service.verify_password("s3cret!", hashed) is True

    def test_verify_rejects_a_wrong_password(self):
        hashed = user_service.get_password_hash("s3cret!")
        assert user_service.verify_password("wrong", hashed) is False


class TestIsAllowedEmail:
    def test_allows_the_listed_domains(self):
        assert user_service.is_allowed_email("jane@uni-muenster.de") is True
        assert user_service.is_allowed_email("jane@fh-swf.de") is True

    def test_allows_subdomains(self):
        assert user_service.is_allowed_email("jane@stud.fh-swf.de") is True

    def test_ignores_case(self):
        assert user_service.is_allowed_email("Jane@Uni-Muenster.DE") is True

    def test_rejects_other_domains(self):
        assert user_service.is_allowed_email("jane@gmail.com") is False

    def test_rejects_lookalike_domains(self):
        assert user_service.is_allowed_email("jane@evil-fh-swf.de") is False
        assert user_service.is_allowed_email("jane@fh-swf.de.evil.com") is False

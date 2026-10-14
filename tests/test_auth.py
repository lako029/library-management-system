import pytest

from library_management_system.services.auth import (
    DEFAULT_ROLES_CLAIM, AuthenticatedUser, authenticated_user_from_claims)


def test_admin_access_depends_on_verified_auth0_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH0_ADMIN_ROLE", "library-admin")
    admin = AuthenticatedUser(
        user_id="user-1",
        email="admin@example.com",
        name="Admin",
        roles=frozenset({"library-admin"}),
    )
    patron = AuthenticatedUser(
        user_id="user-2",
        email="patron@example.com",
        name="Patron",
        roles=frozenset(),
    )

    assert admin.is_admin is True
    assert patron.is_admin is False


def test_authenticated_user_reads_valid_auth0_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH0_ROLES_CLAIM", raising=False)
    claims = {
        "iss": "https://tenant.auth0.com/",
        "sub": "auth0|user-1",
        "aud": ["client-id", "https://library.example.com"],
        "exp": 2_000,
        "email": "admin@example.com",
        "name": "Admin",
        DEFAULT_ROLES_CLAIM: ["Library Admin"],
    }

    user = authenticated_user_from_claims(
        claims,
        expected_issuer="https://tenant.auth0.com/",
        expected_audience="client-id",
        now=1_000,
    )

    assert user.user_id == "auth0|user-1"
    assert user.email == "admin@example.com"
    assert user.name == "Admin"
    assert user.roles == frozenset({"Library Admin"})
    assert user.is_admin is True


@pytest.mark.parametrize(
    ("claim_overrides", "message"),
    (
        ({"iss": "https://attacker.example/"}, "issuer"),
        ({"aud": "another-client"}, "audience"),
        ({"exp": 1_000}, "expired"),
        ({"sub": ""}, "identity"),
        ({DEFAULT_ROLES_CLAIM: "Library Admin"}, "role"),
    ),
)
def test_authenticated_user_rejects_invalid_claims(
    claim_overrides: dict[str, object],
    message: str,
) -> None:
    claims: dict[str, object] = {
        "iss": "https://tenant.auth0.com/",
        "sub": "auth0|user-1",
        "aud": "client-id",
        "exp": 2_000,
        DEFAULT_ROLES_CLAIM: [],
    }
    claims.update(claim_overrides)

    with pytest.raises(ValueError, match=message):
        authenticated_user_from_claims(
            claims,
            expected_issuer="https://tenant.auth0.com/",
            expected_audience="client-id",
            now=1_000,
        )

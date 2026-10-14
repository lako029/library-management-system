import os
import time
from collections.abc import Mapping
from dataclasses import dataclass

ADMIN_ROLE = "Library Admin"
DEFAULT_ROLES_CLAIM = "https://library-management-system/roles"


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str
    name: str
    roles: frozenset[str]

    @property
    def is_admin(self) -> bool:
        admin_role = os.getenv("AUTH0_ADMIN_ROLE", ADMIN_ROLE)
        return admin_role in self.roles


def authenticated_user_from_claims(
    claims: Mapping[str, object],
    *,
    expected_issuer: str,
    expected_audience: str,
    now: float | None = None,
) -> AuthenticatedUser:
    issuer = claims.get("iss")
    if issuer != expected_issuer:
        raise ValueError("Auth0 returned an unexpected token issuer.")

    audience = claims.get("aud")
    audiences = [audience] if isinstance(audience, str) else audience
    if not isinstance(audiences, list) or expected_audience not in audiences:
        raise ValueError("Auth0 token audience does not match this application.")

    expiration = claims.get("exp")
    if (
        not isinstance(expiration, (int, float))
        or isinstance(expiration, bool)
        or expiration <= (time.time() if now is None else now)
    ):
        raise ValueError("Auth0 session has expired. Please sign in again.")

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("Auth0 returned an invalid user identity.")

    roles_claim = os.getenv("AUTH0_ROLES_CLAIM", DEFAULT_ROLES_CLAIM)
    roles = claims.get(roles_claim, [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise ValueError("Auth0 returned invalid role claims.")

    email = claims.get("email", "")
    name = claims.get("name", "")
    return AuthenticatedUser(
        user_id=user_id,
        email=email if isinstance(email, str) else "",
        name=name if isinstance(name, str) else "",
        roles=frozenset(roles),
    )

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.config import get_settings
from library_management_system.dao import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from library_management_system.services.auth import (
    authenticated_user_from_claims,
)
from library_management_system.views import (
    render_admin_view,
    render_sign_in,
    render_user_view,
)
from library_management_system.views.auth import (
    clear_auth_session,
    render_account_sidebar,
)

SessionFactory = sessionmaker[Session]


@st.cache_resource
def get_session_factory() -> SessionFactory:
    engine = create_database_engine()
    if get_settings().auto_create_schema:
        initialize_database(engine)
    return create_session_factory(engine)


def main() -> None:
    settings = get_settings()
    st.set_page_config(page_title="Library", page_icon="📚", layout="wide")
    st.title(settings.app_title)

    try:
        provider_settings = st.secrets.get("auth", {}).get("auth0", {})
    except StreamlitSecretNotFoundError:
        provider_settings = {}
    client_id = provider_settings.get("client_id")
    metadata_url = provider_settings.get("server_metadata_url")
    if not isinstance(client_id, str) or not isinstance(metadata_url, str):
        st.error(
            "Auth0 is not configured. Add the [auth] and [auth.auth0] "
            "sections to .streamlit/secrets.toml; see the README."
        )
        st.stop()

    if not st.user.get("is_logged_in", False):
        render_sign_in()
        st.stop()

    expected_issuer = metadata_url.removesuffix(
        "/.well-known/openid-configuration"
    )
    if not expected_issuer.endswith("/"):
        expected_issuer += "/"

    try:
        user = authenticated_user_from_claims(
            dict(st.user),
            expected_issuer=expected_issuer,
            expected_audience=client_id,
        )
    except ValueError as error:
        clear_auth_session()
        st.error(
            f"Your session could not be validated: {error}. "
            "Please sign in again."
        )
        render_sign_in()
        st.stop()

    render_account_sidebar(user)
    if st.sidebar.button("Sign out"):
        clear_auth_session()

    try:
        sessions = get_session_factory()
    except (RuntimeError, ValueError, SQLAlchemyError) as error:
        st.error(
            f"Database setup failed ({type(error).__name__}). "
            "Check DATABASE_URL, confirm PostgreSQL is running, and try again."
        )
        st.stop()

    view = "User"
    if user.is_admin:
        view = st.sidebar.radio("View", ("User", "Admin"))

    if view == "User":
        render_user_view(sessions, user.user_id)
    else:
        render_admin_view(sessions)


if __name__ == "__main__":
    main()

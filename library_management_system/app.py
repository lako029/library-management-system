import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from streamlit.errors import StreamlitSecretNotFoundError

from library_management_system.config import get_settings
from library_management_system.dao import (create_database_engine,
                                           create_session_factory,
                                           initialize_database)
from library_management_system.services.auth import (
    AuthenticatedUser, authenticated_user_from_claims, local_development_admin)
from library_management_system.views import (render_admin_view, render_sign_in,
                                             render_user_view)
from library_management_system.views.auth import clear_auth_session

SessionFactory = sessionmaker[Session]


@st.cache_resource
def get_session_factory() -> SessionFactory:
    engine = create_database_engine()
    if get_settings().auto_create_schema:
        initialize_database(engine)
    return create_session_factory(engine)


def main() -> None:
    settings = get_settings()
    st.set_page_config(
        page_title=settings.app_title,
        page_icon="📚",
        layout="wide",
    )
    _apply_app_styles()

    if settings.environment == "local":
        user = local_development_admin()
    else:
        try:
            provider_settings = st.secrets.get("auth", {}).get("auth0", {})
        except StreamlitSecretNotFoundError:
            st.error(
                "Auth0 is not configured. Add the [auth] and [auth.auth0] "
                "sections to Streamlit secrets; see the README."
            )
            st.stop()
        client_id = provider_settings.get("client_id")
        metadata_url = provider_settings.get("server_metadata_url")
        if not isinstance(client_id, str) or not isinstance(metadata_url, str):
            st.error(
                "Auth0 is not configured. Add the [auth] and [auth.auth0] "
                "sections to Streamlit secrets; see the README."
            )
            st.stop()

        if not st.user.get("is_logged_in", False):
            _render_app_header()
            render_sign_in()
            st.stop()

        expected_issuer = metadata_url.removesuffix("/.well-known/openid-configuration")
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

    view = _render_app_header(user)

    try:
        sessions = get_session_factory()
    except (RuntimeError, ValueError, SQLAlchemyError) as error:
        st.error(
            f"Database setup failed ({type(error).__name__}). "
            "Check DATABASE_URL, confirm PostgreSQL is running, and try again."
        )
        st.stop()

    if view == "User":
        render_user_view(sessions, user.user_id)
    else:
        render_admin_view(sessions)


def _render_app_header(user: AuthenticatedUser | None = None) -> str:
    brand_column, account_column = st.columns([3, 2], vertical_alignment="center")
    with brand_column:
        st.markdown(
            """
            <div class="library-wordmark">
                <span class="library-wordmark-icon">📚</span>
                <span>The Reading Room</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    view = "User"
    with account_column:
        if user is None:
            return view

        if user.is_admin:
            identity_column, view_column, sign_out_column = st.columns(
                [1.5, 1.1, 0.8],
                vertical_alignment="center",
            )
            with identity_column:
                st.text(user.name or user.email or "Signed-in user")
            with view_column:
                selected_view = st.segmented_control(
                    "View",
                    ("User", "Admin"),
                    default="User",
                    label_visibility="collapsed",
                    key="app_view",
                )
                view = selected_view or "User"
        else:
            identity_column, sign_out_column = st.columns(
                [2, 0.8],
                vertical_alignment="center",
            )
            with identity_column:
                st.text(user.name or user.email or "Signed-in user")

        with sign_out_column:
            if st.button("Sign out", use_container_width=True):
                clear_auth_session()

    return view


def _apply_app_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --library-ink: #20312b;
            --library-muted: #68766f;
            --library-green: #28634f;
            --library-paper: #f5f5f0;
            --library-line: #e3e7e1;
        }
        [data-testid="stAppViewContainer"] {
            background: var(--library-paper);
        }
        [data-testid="stMainBlockContainer"] {
            max-width: 1220px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        section[data-testid="stSidebar"] {
            width: 250px !important;
            min-width: 250px !important;
            background: #eef1eb;
            border-right: 1px solid var(--library-line);
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stAppDeployButton"] {
            display: none;
        }
        h1, h2, h3 {
            color: var(--library-ink);
            letter-spacing: -0.035em;
        }
        h1 {
            font-size: clamp(2rem, 4vw, 2.8rem);
            font-weight: 720;
        }
        [data-testid="stCaptionContainer"] {
            color: var(--library-muted);
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--library-line);
            border-radius: 16px;
            background: #fff;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-librarian_panel) {
            border-color: #d5e3d9;
            background: linear-gradient(155deg, #ffffff 0%, #f2f7f1 100%);
            box-shadow: 0 18px 42px rgba(32, 49, 43, 0.09);
        }
        .librarian-heading {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            margin: 0.1rem 0 0.75rem;
        }
        .librarian-avatar {
            display: grid;
            width: 2.8rem;
            height: 2.8rem;
            flex: 0 0 auto;
            place-items: center;
            border: 1px solid #d4e6d9;
            border-radius: 14px;
            background: linear-gradient(145deg, #e8f3e9, #d7e9dc);
            font-size: 1.35rem;
        }
        .librarian-eyebrow {
            color: #527463;
            font-size: 0.67rem;
            font-weight: 750;
            letter-spacing: 0.11em;
            text-transform: uppercase;
        }
        .librarian-title {
            color: var(--library-ink);
            font-size: 1.25rem;
            font-weight: 750;
            letter-spacing: -0.035em;
            line-height: 1.25;
        }
        .librarian-intro {
            margin: 0 0 0.65rem;
            color: #56665e;
            font-size: 0.91rem;
            line-height: 1.5;
        }
        .st-key-clear_librarian_chat button {
            min-height: 2rem;
            padding: 0.25rem 0.5rem;
            border-color: #dce7de;
            border-radius: 9px;
            background: rgba(255, 255, 255, 0.75);
            color: #52665a;
            font-size: 0.76rem;
        }
        .librarian-empty-state {
            display: flex;
            min-height: 190px;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 1rem 0.65rem;
            text-align: center;
        }
        .librarian-sparkle {
            display: grid;
            width: 2.4rem;
            height: 2.4rem;
            margin-bottom: 0.65rem;
            place-items: center;
            border-radius: 50%;
            background: #e6f1e7;
            color: #367254;
            font-size: 1.3rem;
        }
        .librarian-empty-title {
            color: var(--library-ink);
            font-size: 0.98rem;
            font-weight: 700;
        }
        .librarian-suggestions {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 0.35rem;
        }
        .librarian-suggestion {
            padding: 0.28rem 0.48rem;
            border-radius: 8px;
            background: #fff;
            color: #52645a;
            font-size: 0.7rem;
            box-shadow: 0 1px 3px rgba(32, 49, 43, 0.07);
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-librarian_panel)
        [data-testid="stChatMessage"] {
            border: 1px solid #e5ece6;
            border-radius: 13px;
            background: rgba(255, 255, 255, 0.9);
        }
        [data-testid="stChatInput"] textarea {
            min-height: 88px !important;
            resize: vertical;
        }
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div {
            border-color: #dce3dc;
            border-radius: 10px;
            background: #fff;
        }
        button[kind="primary"] {
            border-radius: 10px;
            font-weight: 650;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 0.6rem;
            border-bottom-color: var(--library-line);
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            color: var(--library-muted);
            font-weight: 600;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            color: var(--library-green);
        }
        .library-wordmark {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin: 0.15rem 0 1.65rem;
            color: var(--library-ink);
            font-size: 1rem;
            font-weight: 750;
            letter-spacing: -0.02em;
        }
        .library-wordmark-icon {
            display: grid;
            width: 2rem;
            height: 2rem;
            place-items: center;
            border-radius: 10px;
            background: #dce9df;
            font-size: 1.1rem;
        }
        .availability-badge {
            display: inline-block;
            padding: 0.28rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 650;
        }
        .availability-available {
            color: #236147;
            background: #e6f2e9;
        }
        .availability-borrowed {
            color: #875b20;
            background: #f8efdc;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

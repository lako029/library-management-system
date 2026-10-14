import streamlit as st

from library_management_system.services.auth import AuthenticatedUser


def render_sign_in() -> None:
    _, welcome_column, _ = st.columns([1, 1.4, 1])
    with welcome_column:
        with st.container(border=True):
            st.markdown("### 📖")
            st.title("Welcome to your library")
            st.write(
                "Find your next favorite, keep track of what you borrow, "
                "and get a little help choosing what to read."
            )
            if st.button(
                "Sign in or create an account",
                type="primary",
                use_container_width=True,
            ):
                st.login("auth0")


def render_account_sidebar(user: AuthenticatedUser) -> None:
    identity = user.name or user.email or "Signed-in user"
    st.sidebar.caption(f"Signed in as {identity}")


def clear_auth_session() -> None:
    st.logout()

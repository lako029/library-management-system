import streamlit as st

from library_management_system.services.auth import AuthenticatedUser


def render_sign_in() -> None:
    st.title("Sign in to the Library")
    st.write("Sign in or create an account using Auth0.")
    if st.button("Sign in or sign up", type="primary"):
        st.login("auth0")


def render_account_sidebar(user: AuthenticatedUser) -> None:
    identity = user.name or user.email or "Signed-in user"
    st.sidebar.caption(f"Signed in as {identity}")


def clear_auth_session() -> None:
    st.logout()

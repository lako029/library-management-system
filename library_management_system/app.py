import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.config import get_settings
from library_management_system.dao import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from library_management_system.views import render_admin_view, render_user_view

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
        sessions = get_session_factory()
    except (RuntimeError, ValueError, SQLAlchemyError) as error:
        st.error(
            f"Database setup failed ({type(error).__name__}). "
            "Check DATABASE_URL, confirm PostgreSQL is running, and try again."
        )
        st.stop()

    view = st.sidebar.radio(
        "View",
        ("User", "Admin"),
        help="Local development view switcher; this does not enforce permissions.",
    )
    st.sidebar.caption("Local demo role selector — not authentication.")

    if view == "User":
        render_user_view(sessions)
    else:
        render_admin_view(sessions)


if __name__ == "__main__":
    main()

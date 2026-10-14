# Library Management System

## Data model

The initial SQLAlchemy model is `library_management_system.dao.Book`. It stores a book title and
author, optional catalog metadata and synopsis, a single current availability
state, and an optional pgvector synopsis embedding for future recommendations.
The current model tracks availability only; it does not yet record borrower
identity or checkout history.

The embedding column is not assigned a fixed vector dimension yet. Select the
embedding model before adding database migrations or vector indexes so the
stored vectors and index configuration match that model.

Pydantic request and response schemas are available from
`library_management_system.data_models`: `BookCreate`, `BookUpdate`, and
`BookRead`, with shared catalog fields defined by `BookBase`. Update schemas
require the complete current book data; nullable metadata may be sent as
`null` to clear it. The read schema is configured to load values from SQLAlchemy
objects and intentionally omits embeddings.

## Database access

Set `DATABASE_URL` to a PostgreSQL URL, for example
`postgresql+psycopg://library:library@localhost:5432/library`. The DAO accepts
an injected SQLAlchemy session, so callers can share a transaction:

```python
from library_management_system.dao import (
    BookDAO,
    create_database_engine,
    create_session_factory,
    session_scope,
)

engine = create_database_engine()
sessions = create_session_factory(engine)
with session_scope(sessions) as session:
    books = BookDAO(session)
    # Call books.create(...), books.search(...), etc.
```

For local development, call `initialize_database(engine)` once to enable
pgvector and create missing tables. This is a bootstrap helper, not a schema
migration strategy. `BookDAO` provides create/read/update/delete, catalog
search, check-in/check-out transitions, and synopsis-embedding recommendations
ranked by Euclidean distance. DAO methods flush changes; `session_scope`
commits successful transactions and rolls back failures. Availability
transitions acquire a row lock until the transaction completes.

## Library assistant

`library_management_system.agent.agent.create_library_agent()` creates the
LangChain assistant using the system prompt in
`library_management_system.agent.prompt`. By default it includes
`search_books` and `recommend_books`; `create_library_agent(tools=[...])` can
instead use custom tools. `run_agent(user_input)` runs a single request.
The User view includes an “Ask the librarian” chat with per-session
conversation history, using the same database session factory as the catalog
UI. Live chat and recommendations require a valid `OPENAI_API_KEY`.

Synopsis recommendations use OpenAI's `text-embedding-3-small` model with
1,536-dimensional embeddings and Euclidean distance through pgvector. Adding or
changing a synopsis in the admin UI stores its embedding, and recommendations
embed the reader's request at query time. These features require
`OPENAI_API_KEY`. Books created before embedding generation was added need their
synopses re-saved or otherwise re-indexed to be included in recommendations.

## Local Streamlit UI

With Docker Postgres running and `DATABASE_URL` set in a local `.env` file,
run the app in the local environment:

```bash
APP_ENV=local uv run --env-file .env streamlit run library_management_system/app.py
```

Signed-in users can browse the catalog and use the librarian assistant. The
Admin view is available only to accounts assigned the configured Auth0 role. The
app initializes pgvector and creates missing tables on startup for convenience
in local development; use migrations for ongoing schema changes.

## Authentication

The app uses Auth0 Universal Login for hosted email/password and Google
authentication. Create an Auth0 **Regular Web Application**; do not use a
single-page application, because the server-side authorization-code exchange
uses the application client secret.

Configure the Auth0 application:

1. Enable a database connection with sign-ups enabled and enable it for this
   application.
2. Enable the Google social connection for this application. Configure Google
   credentials in Auth0 before using Google sign-in beyond development.
3. Add `http://localhost:8501/oauth2callback` to **Allowed Callback URLs**.
   Add `https://your-render-service.onrender.com/oauth2callback` there when
   deploying.
4. Add `http://localhost:8501/oauth2callback` to **Allowed Logout URLs** too.
   Streamlit's `st.logout()` ends the Auth0 session and uses its configured
   OIDC callback URI as the post-logout return URL. Add the Render
   `https://your-render-service.onrender.com/oauth2callback` URI there when
   deploying.
5. In Auth0, create a **Post Login** Action, add it to the Login flow, and use
   this code to include assigned Auth0 roles in the verified ID token:

   ```javascript
   exports.onExecutePostLogin = async (event, api) => {
     const roles = event.authorization?.roles ?? [];
     api.idToken.setCustomClaim(
       "https://library-management-system/roles",
       roles
     );
   };
   ```

Create the Streamlit secrets file from the example:

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` with your Auth0 domain, application client ID,
and client secret. Replace `cookie_secret` with a long random value (for
example, generate one with `openssl rand -hex 32`). The actual `secrets.toml`
is git-ignored and must never be committed.

The app uses Streamlit's built-in OIDC login (`st.login`) with Auth0. Streamlit
handles the authorization redirect, callback, state/nonce checks, and signed
browser session cookie. This avoids keeping OAuth state in transient
`st.session_state`, which can be reset during the redirect. The app checks the
Auth0 issuer, audience, and ID-token expiry before authorizing a user. Streamlit
stores the identity in its signed cookie; the app does not put an ID or access
token in the callback URL. Sign-out clears the local app session; Auth0 may keep
its own browser session active.

To enable the Admin view, create an Auth0 role named `Library Admin` and assign
it only to authorized accounts. The Post Login Action adds assigned roles to
the namespaced claim shown above. The app grants Admin access only when that
verified claim contains the configured role. Set `AUTH0_ADMIN_ROLE` to change
the role name, or `AUTH0_ROLES_CLAIM` to change the namespaced claim key.
Regular sign-ups do not receive the Admin role automatically.

## Environments

Non-secret environment settings live in
`library_management_system/environments/local.toml` and
`library_management_system/environments/production.toml`. Select one with
`APP_ENV=local` or `APP_ENV=production`; `local` is the default.

The local configuration enables the pgvector extension and creates missing
tables at app startup. Production disables automatic schema creation; apply
database migrations before deploying. Set secrets such as `DATABASE_URL` and
`OPENAI_API_KEY` through local environment variables or `.env` locally, and
through the hosting provider's environment settings in production. Never put
secret values in the TOML files.

## Tests

Install the development dependency group and run the unit tests with:

```bash
uv sync --group dev
uv run pytest
```

The unit tests use mocks and in-memory SQLite where practical; they do not
require Docker Postgres or OpenAI credentials.

To add the sample catalog of 20 varied books and generate synopsis embeddings,
run:

```bash
uv run --env-file .env python -m library_management_system.seed_books
```

The command skips title/author pairs already in the database and requires
`OPENAI_API_KEY` to generate embeddings. The short sample synopses are original
summaries, not copied publisher or Goodreads descriptions.
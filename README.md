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

The sidebar switches between a catalog user view and an admin catalog
management view. The role selector is for local development only; it is not
authentication or an authorization boundary. The app initializes pgvector and
creates missing tables on startup for convenience; use migrations for ongoing
schema changes.

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
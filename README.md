# The Reading Room

A library management app built with Streamlit, PostgreSQL, and pgvector. Readers
can search and borrow books, get AI-powered recommendations, and manage returns.
Librarians can manage the catalog and see reader ratings.

## Features

- Search books by title, author, ISBN, genre, synopsis, and availability.
- Add, edit, and delete books in the admin view.
- Check books out and return them; add an optional rating on return.
- Ask the AI librarian to find or recommend books and manage your own loans.
- Sign in with Auth0; administrators receive access through an Auth0 role.

## Requirements

- Python 3.11 or newer and [uv](https://docs.astral.sh/uv/)
- PostgreSQL with the [pgvector extension](https://github.com/pgvector/pgvector)
- An OpenAI API key for embeddings and AI features (optional for basic browsing)

## Run locally

1. Install the project and development dependencies:

   ```bash
   uv sync --group dev
   ```

2. Create a PostgreSQL database with pgvector available. Add a `.env` file in
   the repository root:

   ```dotenv
   DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/DATABASE
   OPENAI_API_KEY=your-openai-api-key
   ```

3. Start the app:

   ```bash
   uv run --env-file .env streamlit run library_management_system/app.py
   ```

   Open <http://localhost:8501>. Local mode does not use OAuth or require
   Auth0 configuration: it signs in automatically as a development admin so
   you can test both the user and admin views. Local mode also enables pgvector
   and creates missing database tables on startup.

### Production Auth0 access

Production uses Auth0 sign-in. Create an Auth0 role named `Library Admin` and
assign it to administrator accounts. Add a Post Login Action to the Auth0 Login
flow to include assigned roles in the ID token:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  api.idToken.setCustomClaim(
    "https://library-management-system/roles",
    event.authorization?.roles ?? []
  );
};
```

Regular users can sign in without this role. Configure Auth0 credentials and
the callback URL in Streamlit secrets using
`.streamlit/secrets.toml.example` as a template. Never commit the populated
secrets file.

## Optional catalog scripts

Add the sample books and generate their embeddings:

```bash
uv run --env-file .env python scripts/seed_books.py
```

Refresh embeddings for books already in the database:

```bash
uv run --env-file .env python scripts/reindex_embeddings.py
```

Both commands require a configured database and `OPENAI_API_KEY`.

## Tests

```bash
uv run pytest
```

Tests use mocks and in-memory SQLite where practical; they do not need database
or OpenAI credentials.

## Deployment notes

Configure `DATABASE_URL`, `OPENAI_API_KEY`, and the Auth0 Streamlit secrets in
the hosting environment. Set `APP_ENV=production` to enable OAuth; unlike local
mode, production does not create database tables automatically, so provision
the schema before launching the app.

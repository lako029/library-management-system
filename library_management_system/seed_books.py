from sqlalchemy import select

from library_management_system.dao import (
    Book,
    BookAvailability,
    BookDAO,
    create_database_engine,
    create_session_factory,
    session_scope,
)
from library_management_system.data_models import BookCreate
from library_management_system.services import get_embeddings

SEED_BOOKS = (
    {
        "title": "1984",
        "author": "George Orwell",
        "genre": "Dystopian fiction",
        "publication_year": 1949,
        "synopsis": (
            "In a surveillance state, a government clerk begins to question "
            "the official version of history and the limits placed on private life."
        ),
    },
    {
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "genre": "Literary fiction",
        "publication_year": 1960,
        "synopsis": (
            "A young girl observes her small Southern town as her father "
            "defends a Black man accused of a serious crime."
        ),
    },
    {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "genre": "Romance",
        "publication_year": 1813,
        "synopsis": (
            "Elizabeth Bennet navigates family expectations, social status, "
            "and her changing judgments of the reserved Mr. Darcy."
        ),
    },
    {
        "title": "The Hobbit",
        "author": "J. R. R. Tolkien",
        "genre": "Fantasy",
        "publication_year": 1937,
        "synopsis": (
            "A comfort-loving hobbit joins a company of dwarves on a perilous "
            "journey to reclaim their mountain home and its treasure."
        ),
    },
    {
        "title": "Dune",
        "author": "Frank Herbert",
        "genre": "Science fiction",
        "publication_year": 1965,
        "synopsis": (
            "On a desert planet prized for its rare resource, a young heir "
            "becomes involved in political conflict and a people's struggle."
        ),
    },
    {
        "title": "Murder on the Orient Express",
        "author": "Agatha Christie",
        "genre": "Mystery",
        "publication_year": 1934,
        "synopsis": (
            "When a passenger is found dead during a snowbound train journey, "
            "detective Hercule Poirot questions the other travelers."
        ),
    },
    {
        "title": "The Shining",
        "author": "Stephen King",
        "genre": "Horror",
        "publication_year": 1977,
        "synopsis": (
            "A family caring for an isolated mountain hotel through winter "
            "encounters disturbing events tied to the building."
        ),
    },
    {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "genre": "Classic fiction",
        "publication_year": 1925,
        "synopsis": (
            "A narrator becomes drawn into the world of a wealthy neighbor "
            "whose lavish parties conceal a longing for the past."
        ),
    },
    {
        "title": "The Martian",
        "author": "Andy Weir",
        "genre": "Science fiction",
        "publication_year": 2011,
        "synopsis": (
            "Stranded alone on Mars after a mission evacuation, an astronaut "
            "uses engineering and improvisation to stay alive."
        ),
    },
    {
        "title": "Educated",
        "author": "Tara Westover",
        "genre": "Memoir",
        "publication_year": 2018,
        "synopsis": (
            "A woman raised in an isolated family describes her path to formal "
            "education and the personal costs of changing her life."
        ),
    },
    {
        "title": "Sapiens",
        "author": "Yuval Noah Harari",
        "genre": "History",
        "publication_year": 2011,
        "synopsis": (
            "A broad account of human history considers how biology, culture, "
            "agriculture, and shared ideas shaped societies."
        ),
    },
    {
        "title": "The Name of the Rose",
        "author": "Umberto Eco",
        "genre": "Historical mystery",
        "publication_year": 1980,
        "synopsis": (
            "A friar investigates a series of deaths in a medieval abbey "
            "whose library holds secrets and contested ideas."
        ),
    },
    {
        "title": "The Handmaid's Tale",
        "author": "Margaret Atwood",
        "genre": "Dystopian fiction",
        "publication_year": 1985,
        "synopsis": (
            "In a theocratic society that controls reproduction, a woman "
            "recounts her constrained life and efforts to retain her identity."
        ),
    },
    {
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "genre": "Science fiction",
        "publication_year": 2021,
        "synopsis": (
            "An astronaut wakes alone on a distant mission with no memory "
            "and must solve a crisis threatening life on Earth."
        ),
    },
    {
        "title": "The Little Prince",
        "author": "Antoine de Saint-Exupéry",
        "genre": "Fable",
        "publication_year": 1943,
        "synopsis": (
            "A pilot stranded in the desert meets a young traveler whose "
            "stories reflect on friendship, care, and how adults see the world."
        ),
    },
    {
        "title": "The Book Thief",
        "author": "Markus Zusak",
        "genre": "Historical fiction",
        "publication_year": 2005,
        "synopsis": (
            "In wartime Germany, a foster child finds connection through "
            "books while her family shelters a Jewish man."
        ),
    },
    {
        "title": "The Silent Patient",
        "author": "Alex Michaelides",
        "genre": "Thriller",
        "publication_year": 2019,
        "synopsis": (
            "A psychotherapist becomes fixated on understanding why a painter "
            "stopped speaking after a violent event."
        ),
    },
    {
        "title": "The Midnight Library",
        "author": "Matt Haig",
        "genre": "Fantasy",
        "publication_year": 2020,
        "synopsis": (
            "Between life and death, a woman explores alternate versions of "
            "her life and considers the choices that shaped them."
        ),
    },
    {
        "title": "Born a Crime",
        "author": "Trevor Noah",
        "genre": "Memoir",
        "publication_year": 2016,
        "synopsis": (
            "The comedian recounts growing up in South Africa during and "
            "after apartheid, focusing on family, identity, and resilience."
        ),
    },
    {
        "title": "The Alchemist",
        "author": "Paulo Coelho",
        "genre": "Adventure fiction",
        "publication_year": 1988,
        "synopsis": (
            "A young shepherd travels beyond his home in search of treasure "
            "and reflects on purpose, change, and the journey itself."
        ),
    },
)


def seed_books() -> int:
    engine = create_database_engine()
    sessions = create_session_factory(engine)
    try:
        with session_scope(sessions) as session:
            existing_books = session.execute(
                select(Book.title, Book.author)
            ).all()
            existing = {
                (title.casefold(), author.casefold())
                for title, author in existing_books
            }
            new_books = [
                book
                for book in SEED_BOOKS
                if (book["title"].casefold(), book["author"].casefold())
                not in existing
            ]

        if not new_books:
            return 0

        embeddings = get_embeddings().embed_documents(
            [book["synopsis"] for book in new_books]
        )
        if len(embeddings) != len(new_books):
            raise RuntimeError("Embedding service returned an unexpected result count.")

        with session_scope(sessions) as session:
            dao = BookDAO(session)
            for book_data, embedding in zip(new_books, embeddings, strict=True):
                data = BookCreate(
                    **book_data,
                    language="English",
                    availability=BookAvailability.AVAILABLE,
                )
                dao.create(data, synopsis_embedding=embedding)
        return len(new_books)
    finally:
        engine.dispose()


def main() -> None:
    added = seed_books()
    print(f"Added {added} book(s).")


if __name__ == "__main__":
    main()

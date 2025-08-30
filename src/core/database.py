from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
import logging
import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/database/hbi.db"

# Engine will be created during initialization
engine = None
SessionLocal = None
Base = declarative_base()


def get_db() -> Session:
    """
    Dependency function to get database session.
    Yields a database session and ensures it's closed after use.
    """
    if SessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call initialize_database() first."
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_fts5_tables():
    """
    Create FTS5 virtual tables for full-text search on chunks.
    This function should be called after Base.metadata.create_all().
    """
    if engine is None:
        raise RuntimeError(
            "Database engine not initialized. Call initialize_database() first."
        )

    try:
        with engine.connect() as conn:
            # Create FTS5 virtual table for chunks
            # This allows efficient full-text search on chunk_text
            conn.execute(
                text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_text,
                    content='chunks',
                    content_rowid='id'
                )
            """)
            )

            # Create triggers to keep FTS table in sync with main table
            conn.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON chunks
                BEGIN
                    INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
                END
            """)
            )

            conn.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON chunks
                BEGIN
                    DELETE FROM chunks_fts WHERE rowid = old.id;
                END
            """)
            )

            conn.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE ON chunks
                BEGIN
                    UPDATE chunks_fts SET chunk_text = new.chunk_text WHERE rowid = new.id;
                END
            """)
            )

            conn.commit()
            logging.info("Successfully created FTS5 tables and triggers")

    except Exception as e:
        logging.error(f"Failed to create FTS5 tables: {str(e)}")
        raise


def initialize_database():
    """
    Initialize the database by creating all tables and FTS5 virtual tables.
    Call this function once during application startup.
    """
    global engine, SessionLocal

    try:
        # Ensure database directory exists
        db_path = "./data/database/hbi.db"
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logging.info(f"Created database directory: {db_dir}")

        # Create engine and session maker
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            connect_args={"check_same_thread": False},  # Needed for SQLite
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Create regular SQLAlchemy tables
        Base.metadata.create_all(bind=engine)

        # Create FTS5 virtual tables
        create_fts5_tables()

        # Seed LLM configurations
        try:
            from .seed_llm_configurations import initialize_llm_configurations

            initialize_llm_configurations()
            logging.info("LLM configurations seeded successfully")
        except Exception as e:
            logging.warning(f"Failed to seed LLM configurations: {str(e)}")

        logging.info("Database initialization completed successfully")

    except Exception as e:
        logging.error(f"Database initialization failed: {str(e)}")
        raise

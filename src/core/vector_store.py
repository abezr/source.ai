"""
Vector store module for HBI system.
Handles vector embeddings storage and retrieval using sqlite-vec.
"""

import sqlite3
import json
import logging
from typing import List, Tuple, Optional
import numpy as np

from .database import SQLALCHEMY_DATABASE_URL


class VectorStore:
    """
    SQLite-vec based vector store for managing embeddings.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize the vector store.

        Args:
            db_path: Path to SQLite database file. If None, uses the main database.
        """
        if db_path is None:
            # Extract path from SQLAlchemy URL
            if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
                db_path = SQLALCHEMY_DATABASE_URL[10:]  # Remove 'sqlite:///'
            else:
                db_path = "./data/database/hbi.db"

        self.db_path = db_path
        self._ensure_vector_table()

    def _ensure_vector_table(self):
        """Ensure the vector embeddings table exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Enable sqlite-vec extension
                conn.enable_load_extension(True)
                conn.load_extension("sqlite_vec")

                # Create vector table if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_embeddings (
                        chunk_id INTEGER PRIMARY KEY,
                        embedding TEXT NOT NULL,  -- JSON array of floats
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create vector index for efficient similarity search
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings_vec USING vec0(
                        chunk_id INTEGER PRIMARY KEY,
                        embedding float[384]  -- Adjust dimension based on your embedding model
                    )
                """)

                conn.commit()
                logging.info("Vector store tables initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize vector store: {str(e)}")
            raise

    def store_embedding(self, chunk_id: int, embedding: List[float]) -> bool:
        """
        Store an embedding vector for a chunk.

        Args:
            chunk_id: The chunk ID
            embedding: The embedding vector as a list of floats

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.enable_load_extension(True)
                conn.load_extension("sqlite_vec")

                # Store embedding as JSON for backup
                embedding_json = json.dumps(embedding)

                # Insert into regular table
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding)
                    VALUES (?, ?)
                """,
                    (chunk_id, embedding_json),
                )

                # Insert into vector table for fast search
                # Convert to numpy array for sqlite-vec
                embedding_array = np.array(embedding, dtype=np.float32)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chunk_embeddings_vec (chunk_id, embedding)
                    VALUES (?, ?)
                """,
                    (chunk_id, embedding_array.tobytes()),
                )

                conn.commit()
                logging.debug(f"Stored embedding for chunk {chunk_id}")
                return True

        except Exception as e:
            logging.error(f"Failed to store embedding for chunk {chunk_id}: {str(e)}")
            return False

    def search_similar(
        self, query_embedding: List[float], limit: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Search for similar embeddings using cosine similarity.

        Args:
            query_embedding: The query embedding vector
            limit: Maximum number of results to return

        Returns:
            List of (chunk_id, similarity_score) tuples
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.enable_load_extension(True)
                conn.load_extension("sqlite_vec")

                # Convert query embedding to numpy array
                query_array = np.array(query_embedding, dtype=np.float32)

                # Perform vector similarity search
                cursor = conn.execute(
                    """
                    SELECT chunk_id, distance
                    FROM chunk_embeddings_vec
                    WHERE embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                """,
                    (query_array.tobytes(), limit),
                )

                results = [(row[0], row[1]) for row in cursor.fetchall()]
                logging.debug(f"Found {len(results)} similar chunks")
                return results

        except Exception as e:
            logging.error(f"Failed to search similar embeddings: {str(e)}")
            return []

    def get_embedding(self, chunk_id: int) -> Optional[List[float]]:
        """
        Retrieve an embedding vector for a chunk.

        Args:
            chunk_id: The chunk ID

        Returns:
            The embedding vector as a list of floats, or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT embedding FROM chunk_embeddings
                    WHERE chunk_id = ?
                """,
                    (chunk_id,),
                )

                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None

        except Exception as e:
            logging.error(
                f"Failed to retrieve embedding for chunk {chunk_id}: {str(e)}"
            )
            return None

    def delete_embedding(self, chunk_id: int) -> bool:
        """
        Delete an embedding for a chunk.

        Args:
            chunk_id: The chunk ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.enable_load_extension(True)
                conn.load_extension("sqlite_vec")

                # Delete from both tables
                conn.execute(
                    "DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,)
                )
                conn.execute(
                    "DELETE FROM chunk_embeddings_vec WHERE chunk_id = ?", (chunk_id,)
                )

                conn.commit()
                logging.debug(f"Deleted embedding for chunk {chunk_id}")
                return True

        except Exception as e:
            logging.error(f"Failed to delete embedding for chunk {chunk_id}: {str(e)}")
            return False

    def get_stats(self) -> dict:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM chunk_embeddings")
                count = cursor.fetchone()[0]

                return {
                    "total_embeddings": count,
                    "embedding_dimension": 384,  # Based on our model
                    "database_path": self.db_path,
                }

        except Exception as e:
            logging.error(f"Failed to get vector store stats: {str(e)}")
            return {"error": str(e)}


# Global vector store instance
_vector_store = None


def get_vector_store() -> VectorStore:
    """
    Get the global vector store instance.

    Returns:
        VectorStore instance
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store

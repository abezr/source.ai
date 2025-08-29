from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple
import logging
from . import models, schemas
from .graph import get_graph_driver
from .vector_store import get_vector_store
from ..agents.parser import chunk_and_embed_book


def create_book(db: Session, book: schemas.BookCreate) -> models.Book:
    """
    Create a new book record in the database.

    Args:
        db: Database session
        book: Book creation data

    Returns:
        The created book instance
    """
    db_book = models.Book(
        title=book.title,
        author=book.author,
        source_path=None  # Initially None, can be set later
    )
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book


def get_book(db: Session, book_id: int) -> models.Book | None:
    """
    Retrieve a book by its ID.

    Args:
        db: Database session
        book_id: The book ID to retrieve

    Returns:
        The book instance if found, None otherwise
    """
    return db.query(models.Book).filter(models.Book.id == book_id).first()


def get_books(db: Session, skip: int = 0, limit: int = 100) -> list[models.Book]:
    """
    Retrieve a list of books with pagination.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of book instances
    """
    return db.query(models.Book).offset(skip).limit(limit).all()


def create_book_toc_graph(book_id: int, toc_nodes: List[schemas.TOCNode]) -> bool:
    """
    Create a hierarchical graph structure in Neo4j for a book's Table of Contents.

    Args:
        book_id: The ID of the book
        toc_nodes: List of TOCNode objects representing the hierarchical structure

    Returns:
        True if successful, False otherwise
    """
    try:
        driver = get_graph_driver()

        with driver.session() as session:
            # First, create or ensure the book node exists
            session.run(
                """
                MERGE (b:Book {id: $book_id})
                ON CREATE SET b.created_at = datetime()
                ON MATCH SET b.updated_at = datetime()
                """,
                book_id=book_id
            )

            # Create the hierarchical structure
            _create_toc_nodes_recursive(session, book_id, toc_nodes, None)

        logging.info(f"Successfully created ToC graph for book {book_id}")
        return True

    except Exception as e:
        logging.error(f"Failed to create ToC graph for book {book_id}: {str(e)}")
        return False


def _create_toc_nodes_recursive(session, book_id: int, toc_nodes: List[schemas.TOCNode], parent_id: str = None):
    """
    Recursively create ToC nodes and relationships in Neo4j.

    Args:
        session: Neo4j session
        book_id: The book ID
        toc_nodes: List of TOCNode objects to create
        parent_id: ID of the parent node (None for root level)
    """
    for node in toc_nodes:
        # Create unique node ID
        node_id = f"book_{book_id}_toc_{hash(node.title + str(node.page_number))}"

        # Create the chapter/section node
        session.run(
            """
            MERGE (c:Chapter {id: $node_id})
            ON CREATE SET
                c.title = $title,
                c.page_number = $page_number,
                c.book_id = $book_id,
                c.created_at = datetime()
            ON MATCH SET
                c.updated_at = datetime()
            """,
            node_id=node_id,
            title=node.title,
            page_number=node.page_number,
            book_id=book_id
        )

        # Create relationship to parent (or book if root level)
        if parent_id:
            session.run(
                """
                MATCH (parent {id: $parent_id}), (child {id: $node_id})
                MERGE (parent)-[:HAS_CHILD]->(child)
                """,
                parent_id=parent_id,
                node_id=node_id
            )
        else:
            # Root level - connect to book
            session.run(
                """
                MATCH (b:Book {id: $book_id}), (c:Chapter {id: $node_id})
                MERGE (b)-[:HAS_TOC]->(c)
                """,
                book_id=book_id,
                node_id=node_id
            )

        # Recursively process children
        if node.children:
            _create_toc_nodes_recursive(session, book_id, node.children, node_id)


def get_toc_by_book_id(book_id: int) -> List[schemas.TOCNode]:
    """
    Retrieve the hierarchical Table of Contents for a book from Neo4j.

    Args:
        book_id: The ID of the book

    Returns:
        List of TOCNode objects representing the hierarchical structure
    """
    try:
        driver = get_graph_driver()

        with driver.session() as session:
            # Query to get the hierarchical structure
            result = session.run(
                """
                MATCH path = (b:Book {id: $book_id})-[:HAS_TOC*]->(c:Chapter)
                WITH collect(path) as paths
                CALL apoc.convert.toTree(paths) YIELD value
                RETURN value
                """,
                book_id=book_id
            )

            records = list(result)

            if not records:
                return []

            # Convert the result to TOCNode objects
            toc_data = records[0]["value"]
            return _convert_graph_to_toc_nodes(toc_data)

    except Exception as e:
        logging.error(f"Failed to retrieve ToC for book {book_id}: {str(e)}")
        return []


def _convert_graph_to_toc_nodes(graph_data: dict) -> List[schemas.TOCNode]:
    """
    Convert Neo4j graph data to TOCNode objects.

    Args:
        graph_data: Graph data from Neo4j

    Returns:
        List of TOCNode objects
    """
    toc_nodes = []

    # Process root level chapters
    if 'HAS_TOC' in graph_data:
        for root_chapter in graph_data['HAS_TOC']:
            toc_node = _build_toc_node_from_graph(root_chapter)
            toc_nodes.append(toc_node)

    return toc_nodes


def _build_toc_node_from_graph(chapter_data: dict) -> schemas.TOCNode:
    """
    Build a TOCNode from Neo4j chapter data.

    Args:
        chapter_data: Chapter data from Neo4j

    Returns:
        TOCNode object
    """
    children = []

    # Process children if they exist
    if 'HAS_CHILD' in chapter_data:
        for child in chapter_data['HAS_CHILD']:
            child_node = _build_toc_node_from_graph(child)
            children.append(child_node)

    return schemas.TOCNode(
        title=chapter_data.get('title', ''),
        page_number=chapter_data.get('page_number', 0),
        children=children
    )


def create_book_index_graph(book_id: int, index_entries: List[schemas.IndexEntry]) -> bool:
    """
    Create a graph structure in Neo4j for a book's alphabetical index.

    Args:
        book_id: The ID of the book
        index_entries: List of IndexEntry objects representing index terms and page references

    Returns:
        True if successful, False otherwise
    """
    try:
        driver = get_graph_driver()

        with driver.session() as session:
            # First, create or ensure the book node exists
            session.run(
                """
                MERGE (b:Book {id: $book_id})
                ON CREATE SET b.created_at = datetime()
                ON MATCH SET b.updated_at = datetime()
                """,
                book_id=book_id
            )

            # Create index term nodes and relationships
            for entry in index_entries:
                term_id = f"book_{book_id}_index_{hash(entry.term.lower())}"

                # Create the index term node
                session.run(
                    """
                    MERGE (t:IndexTerm {id: $term_id})
                    ON CREATE SET
                        t.term = $term,
                        t.book_id = $book_id,
                        t.created_at = datetime()
                    ON MATCH SET
                        t.updated_at = datetime()
                    """,
                    term_id=term_id,
                    term=entry.term,
                    book_id=book_id
                )

                # Create relationships to pages
                for page_number in entry.page_numbers:
                    page_id = f"book_{book_id}_page_{page_number}"

                    # Create page node if it doesn't exist
                    session.run(
                        """
                        MERGE (p:Page {id: $page_id})
                        ON CREATE SET
                            p.page_number = $page_number,
                            p.book_id = $book_id,
                            p.created_at = datetime()
                        ON MATCH SET
                            p.updated_at = datetime()
                        """,
                        page_id=page_id,
                        page_number=page_number,
                        book_id=book_id
                    )

                    # Create APPEARS_ON_PAGE relationship
                    session.run(
                        """
                        MATCH (t:IndexTerm {id: $term_id}), (p:Page {id: $page_id})
                        MERGE (t)-[:APPEARS_ON_PAGE]->(p)
                        """,
                        term_id=term_id,
                        page_id=page_id
                    )

                # Create relationship from book to index term
                session.run(
                    """
                    MATCH (b:Book {id: $book_id}), (t:IndexTerm {id: $term_id})
                    MERGE (b)-[:HAS_INDEX_TERM]->(t)
                    """,
                    book_id=book_id,
                    term_id=term_id
                )

        logging.info(f"Successfully created index graph for book {book_id} with {len(index_entries)} entries")
        return True

    except Exception as e:
        logging.error(f"Failed to create index graph for book {book_id}: {str(e)}")
        return False


def get_book_index_terms(book_id: int) -> List[schemas.IndexEntry]:
    """
    Retrieve the alphabetical index terms for a book from Neo4j.

    Args:
        book_id: The ID of the book

    Returns:
        List of IndexEntry objects representing the index terms and their page references
    """
    try:
        driver = get_graph_driver()

        with driver.session() as session:
            # Query to get index terms and their page references
            result = session.run(
                """
                MATCH (b:Book {id: $book_id})-[:HAS_INDEX_TERM]->(t:IndexTerm)-[:APPEARS_ON_PAGE]->(p:Page)
                RETURN t.term as term, collect(p.page_number) as page_numbers
                ORDER BY t.term
                """,
                book_id=book_id
            )

            records = list(result)

            if not records:
                return []

            # Convert to IndexEntry objects
            index_entries = []
            for record in records:
                entry = schemas.IndexEntry(
                    term=record["term"],
                    page_numbers=sorted(record["page_numbers"])
                )
                index_entries.append(entry)

            return index_entries

    except Exception as e:
        logging.error(f"Failed to retrieve index for book {book_id}: {str(e)}")
        return []


def update_book_source_path(db: Session, book_id: int, source_path: str) -> models.Book | None:
    """
    Update the source_path field for a specific book.

    Args:
        db: Database session
        book_id: The ID of the book to update
        source_path: The new source path to set

    Returns:
        The updated book instance if found, None otherwise
    """
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if book:
        book.source_path = source_path
        db.commit()
        db.refresh(book)
    return book


def create_chunks_and_embeddings(db: Session, book_id: int, chunks_with_embeddings: List[Dict[str, Any]]) -> bool:
    """
    Store text chunks and their embeddings in the database.

    Args:
        db: Database session
        book_id: ID of the book the chunks belong to
        chunks_with_embeddings: List of chunk dictionaries with embedding data

    Returns:
        True if successful, False otherwise
    """
    try:
        if not chunks_with_embeddings:
            logging.warning(f"No chunks provided for book {book_id}")
            return True

        logging.info(f"Storing {len(chunks_with_embeddings)} chunks for book {book_id}")

        # Store chunks in SQLite
        for chunk_data in chunks_with_embeddings:
            chunk = models.Chunk(
                book_id=book_id,
                chunk_text=chunk_data['chunk_text'],
                page_number=chunk_data['page_number'],
                chunk_order=chunk_data['chunk_order']
            )
            db.add(chunk)
            db.flush()  # Get the chunk ID for vector storage

            # Store embedding in vector database
            embedding_success = _store_chunk_embedding(chunk.id, chunk_data['embedding'])
            if not embedding_success:
                logging.warning(f"Failed to store embedding for chunk {chunk.id}, continuing...")

        db.commit()
        logging.info(f"Successfully stored {len(chunks_with_embeddings)} chunks for book {book_id}")
        return True

    except Exception as e:
        db.rollback()
        logging.error(f"Failed to store chunks for book {book_id}: {str(e)}")
        return False


def _store_chunk_embedding(chunk_id: int, embedding: List[float]) -> bool:
    """
    Store a chunk's embedding vector in sqlite-vec database.

    Args:
        chunk_id: The chunk ID (used as vector ID)
        embedding: The embedding vector as a list of floats

    Returns:
        True if successful, False otherwise
    """
    try:
        vector_store = get_vector_store()
        success = vector_store.store_embedding(chunk_id, embedding)

        if success:
            logging.debug(f"Stored embedding for chunk {chunk_id} with {len(embedding)} dimensions")
        else:
            logging.error(f"Failed to store embedding for chunk {chunk_id}")

        return success

    except Exception as e:
        logging.error(f"Error storing embedding for chunk {chunk_id}: {str(e)}")
        return False


def get_chunks_by_book_id(db: Session, book_id: int, skip: int = 0, limit: int = 100) -> List[models.Chunk]:
    """
    Retrieve chunks for a specific book.

    Args:
        db: Database session
        book_id: ID of the book
        skip: Number of chunks to skip (pagination)
        limit: Maximum number of chunks to return

    Returns:
        List of Chunk instances
    """
    return db.query(models.Chunk)\
        .filter(models.Chunk.book_id == book_id)\
        .order_by(models.Chunk.chunk_order)\
        .offset(skip)\
        .limit(limit)\
        .all()


def get_chunk_by_id(db: Session, chunk_id: int) -> models.Chunk | None:
    """
    Retrieve a specific chunk by its ID.

    Args:
        db: Database session
        chunk_id: The chunk ID to retrieve

    Returns:
        Chunk instance if found, None otherwise
    """
    return db.query(models.Chunk).filter(models.Chunk.id == chunk_id).first()


def process_book_chunks_and_embeddings(db: Session, book_id: int, file_path: str) -> bool:
    """
    Complete pipeline: chunk book content, generate embeddings, and store everything.

    Args:
        db: Database session
        book_id: ID of the book to process
        file_path: Path to the PDF file

    Returns:
        True if successful, False otherwise
    """
    try:
        logging.info(f"Starting chunk and embed processing for book {book_id}")

        # Use the complete pipeline from parser agent
        chunks_with_embeddings = chunk_and_embed_book(file_path, book_id)

        if not chunks_with_embeddings:
            logging.warning(f"No chunks generated for book {book_id}")
            return False

        # Store chunks and embeddings
        success = create_chunks_and_embeddings(db, book_id, chunks_with_embeddings)

        if success:
            logging.info(f"Successfully processed chunks and embeddings for book {book_id}")
        else:
            logging.error(f"Failed to store chunks and embeddings for book {book_id}")

        return success

    except Exception as e:
        logging.error(f"Failed to process chunks and embeddings for book {book_id}: {str(e)}")
        return False


def lexical_search(db: Session, query: str, limit: int = 10, book_id: int = None) -> List[Tuple[int, float]]:
    """
    Perform lexical search using SQLite FTS5 on chunk text.

    Args:
        db: Database session
        query: Search query string
        limit: Maximum number of results to return
        book_id: Optional book ID to filter results to a specific book

    Returns:
        List of (chunk_id, relevance_score) tuples
    """
    try:
        # Use raw SQL for FTS5 search with BM25 scoring
        base_query = """
            SELECT c.id, bm25(chunks_fts) as score
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.id
            WHERE chunks_fts MATCH ?
        """

        params = [query]

        if book_id is not None:
            base_query += " AND c.book_id = ?"
            params.append(book_id)

        base_query += " ORDER BY bm25(chunks_fts) LIMIT ?"
        params.append(limit)

        result = db.execute(base_query, params).fetchall()

        # Convert results to list of tuples
        search_results = [(row[0], float(row[1])) for row in result]

        logging.debug(f"Lexical search for '{query}' returned {len(search_results)} results")
        return search_results

    except Exception as e:
        logging.error(f"Failed to perform lexical search for query '{query}': {str(e)}")
        return []


def vector_search(query_embedding: List[float], limit: int = 10, book_id: int = None) -> List[Tuple[int, float]]:
    """
    Perform vector similarity search using sqlite-vec.

    Args:
        query_embedding: Query embedding vector
        limit: Maximum number of results to return
        book_id: Optional book ID to filter results to a specific book

    Returns:
        List of (chunk_id, similarity_score) tuples
    """
    try:
        from .vector_store import get_vector_store
        vector_store = get_vector_store()

        # Get all similar chunks
        all_results = vector_store.search_similar(query_embedding, limit=limit * 2)  # Get more for filtering

        if book_id is not None:
            # Filter results to specific book
            from sqlalchemy import text
            from .database import SessionLocal
            temp_db = SessionLocal()

            try:
                # Get chunk IDs that belong to the specified book
                book_chunk_ids = set()
                result = temp_db.execute(
                    text("SELECT id FROM chunks WHERE book_id = ?"),
                    [book_id]
                ).fetchall()

                book_chunk_ids = {row[0] for row in result}

                # Filter vector results to only include chunks from the specified book
                filtered_results = [
                    (chunk_id, score) for chunk_id, score in all_results
                    if chunk_id in book_chunk_ids
                ][:limit]

                return filtered_results

            finally:
                temp_db.close()
        else:
            # Return top results without book filtering
            return all_results[:limit]

    except Exception as e:
        logging.error(f"Failed to perform vector search: {str(e)}")
        return []


def reciprocal_rank_fusion(lexical_results: List[Tuple[int, float]],
                          vector_results: List[Tuple[int, float]],
                          k: int = 60) -> List[Tuple[int, float]]:
    """
    Combine lexical and vector search results using Reciprocal Rank Fusion (RRF).

    Args:
        lexical_results: List of (chunk_id, score) from lexical search
        vector_results: List of (chunk_id, score) from vector search
        k: RRF parameter (typically 60)

    Returns:
        List of (chunk_id, rrf_score) tuples sorted by RRF score
    """
    try:
        # Create dictionaries for quick lookup
        lexical_scores = {chunk_id: score for chunk_id, score in lexical_results}
        vector_scores = {chunk_id: score for chunk_id, score in vector_results}

        # Get all unique chunk IDs
        all_chunk_ids = set(lexical_scores.keys()) | set(vector_scores.keys())

        # Calculate RRF scores
        rrf_scores = {}
        for chunk_id in all_chunk_ids:
            rrf_score = 0.0

            # Add lexical contribution if present
            if chunk_id in lexical_scores:
                lexical_rank = lexical_results.index((chunk_id, lexical_scores[chunk_id])) + 1
                rrf_score += 1.0 / (k + lexical_rank)

            # Add vector contribution if present
            if chunk_id in vector_scores:
                vector_rank = vector_results.index((chunk_id, vector_scores[chunk_id])) + 1
                rrf_score += 1.0 / (k + vector_rank)

            rrf_scores[chunk_id] = rrf_score

        # Sort by RRF score (descending)
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        logging.debug(f"RRF combined {len(lexical_results)} lexical and {len(vector_results)} vector results into {len(sorted_results)} fused results")
        return sorted_results

    except Exception as e:
        logging.error(f"Failed to perform reciprocal rank fusion: {str(e)}")
        # Fallback: return lexical results if RRF fails
        return lexical_results


def hybrid_retrieve(db: Session, query: str, top_k: int = 10, book_id: int = None) -> List[models.Chunk]:
    """
    Perform hybrid retrieval combining lexical and vector search with RRF.

    Args:
        db: Database session
        query: Search query string
        top_k: Number of top results to return
        book_id: Optional book ID to filter results to a specific book

    Returns:
        List of Chunk objects sorted by relevance
    """
    try:
        # Generate embedding for the query
        from ..agents.parser import generate_embeddings_for_chunks
        query_chunks = generate_embeddings_for_chunks([{'chunk_text': query, 'page_number': 0, 'chunk_order': 0}])

        if not query_chunks:
            logging.warning("Failed to generate query embedding, falling back to lexical search")
            # Fallback to lexical search only
            lexical_results = lexical_search(db, query, limit=top_k, book_id=book_id)
            chunk_ids = [chunk_id for chunk_id, _ in lexical_results]
        else:
            query_embedding = query_chunks[0]['embedding']

            # Perform parallel searches
            lexical_results = lexical_search(db, query, limit=top_k * 2, book_id=book_id)
            vector_results = vector_search(query_embedding, limit=top_k * 2, book_id=book_id)

            # Combine results using RRF
            fused_results = reciprocal_rank_fusion(lexical_results, vector_results)

            # Get top_k results
            chunk_ids = [chunk_id for chunk_id, _ in fused_results[:top_k]]

        # Retrieve full Chunk objects
        if chunk_ids:
            chunks = db.query(models.Chunk)\
                .filter(models.Chunk.id.in_(chunk_ids))\
                .all()

            # Sort chunks to match the order from search results
            chunk_order = {chunk_id: i for i, chunk_id in enumerate(chunk_ids)}
            chunks.sort(key=lambda c: chunk_order[c.id])

            logging.info(f"Hybrid search for '{query}' returned {len(chunks)} chunks")
            return chunks
        else:
            logging.info(f"Hybrid search for '{query}' returned no results")
            return []

    except Exception as e:
        logging.error(f"Failed to perform hybrid retrieval for query '{query}': {str(e)}")
        return []
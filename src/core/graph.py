"""
Neo4j graph database client module for HBI system.
Provides dependency injection for Neo4j driver instances.
"""

import os
from typing import Optional
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


class GraphClient:
    """
    Neo4j graph database client with connection management.
    """

    def __init__(self):
        """Initialize the Neo4j driver with environment variables."""
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "neo4jpassword")
        self.driver = None

    def connect(self) -> None:
        """
        Establish connection to Neo4j database.

        Raises:
            ServiceUnavailable: If connection to Neo4j fails
        """
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                # Connection pool settings for production
                max_connection_lifetime=30 * 60,  # 30 minutes
                max_connection_pool_size=50,
                connection_acquisition_timeout=2.0
            )
            # Test the connection
            self.driver.verify_connectivity()
        except ServiceUnavailable as e:
            raise ServiceUnavailable(f"Failed to connect to Neo4j at {self.uri}: {str(e)}")

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def get_driver(self):
        """
        Get the Neo4j driver instance, connecting if necessary.

        Returns:
            Neo4j driver instance
        """
        if not self.driver:
            self.connect()
        return self.driver


# Global client instance
graph_client = GraphClient()


def get_graph_driver():
    """
    Dependency injection function for FastAPI endpoints.
    Provides a Neo4j driver instance.

    Returns:
        Neo4j driver instance

    Raises:
        ServiceUnavailable: If Neo4j connection fails
    """
    return graph_client.get_driver()


def create_session():
    """
    Create a new Neo4j session for transactional operations.

    Returns:
        Neo4j session instance
    """
    driver = get_graph_driver()
    return driver.session()


def execute_query(query: str, parameters: Optional[dict] = None):
    """
    Execute a Cypher query with optional parameters.

    Args:
        query: Cypher query string
        parameters: Optional query parameters

    Returns:
        Query result

    Raises:
        ServiceUnavailable: If Neo4j connection fails
    """
    with create_session() as session:
        result = session.run(query, parameters or {})
        return result
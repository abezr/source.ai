from locust import HttpUser, task, between
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HBIUser(HttpUser):
    # Update host to point to the correct FastAPI server port
    host = "http://localhost:8001"

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks to simulate real user behavior

    # Sample queries from golden_set.jsonl
    queries = [
        "What is the main purpose of the Hybrid Book Index system?",
        "How does the system prevent hallucinations in generated answers?",
        "What are the key components of the system's architecture?",
        "What evaluation metrics does the system use to ensure quality?",
        "How does the hybrid retrieval mechanism work?"
    ]

    @task(10)  # Heavily weighted task for main use case
    def query_endpoint(self):
        query = random.choice(self.queries)
        payload = {
            "query": query,
            "book_id": 1,  # Assume book with ID 1 exists
            "top_k": 10
        }
        try:
            response = self.client.post("/query", json=payload)
            if response.status_code >= 400:
                logger.warning(f"Query endpoint failed with status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Query endpoint error: {e}")
            # Continue execution instead of crashing

    @task(3)  # Moderately weighted task
    def toc_endpoint(self):
        try:
            response = self.client.get("/books/1/toc")
            if response.status_code >= 400:
                logger.warning(f"ToC endpoint failed with status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"ToC endpoint error: {e}")
            # Continue execution instead of crashing

    @task(1)  # Lightly weighted task
    def upload_endpoint(self):
        # Assume sample.pdf exists in load_tests directory
        try:
            with open("load_tests/sample.pdf", "rb") as f:
                files = {"file": ("sample.pdf", f, "application/pdf")}
                response = self.client.post("/books/1/upload", files=files)
                if response.status_code >= 400:
                    logger.warning(f"Upload endpoint failed with status {response.status_code}: {response.text}")
        except FileNotFoundError:
            logger.warning("Sample PDF file not found, skipping upload task")
        except Exception as e:
            logger.error(f"Upload endpoint error: {e}")
            # Continue execution instead of crashing
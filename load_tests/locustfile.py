from locust import HttpUser, task, between
import random
import json

class HBIUser(HttpUser):
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
        self.client.post("/query", json=payload)

    @task(3)  # Moderately weighted task
    def toc_endpoint(self):
        self.client.get("/books/1/toc")

    @task(1)  # Lightly weighted task
    def upload_endpoint(self):
        # Assume sample.pdf exists in load_tests directory
        try:
            with open("load_tests/sample.pdf", "rb") as f:
                files = {"file": ("sample.pdf", f, "application/pdf")}
                self.client.post("/books/1/upload", files=files)
        except FileNotFoundError:
            # If file not found, skip this task
            pass
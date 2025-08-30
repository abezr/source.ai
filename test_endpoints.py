import requests

# Test the health endpoint
print("Testing health endpoint...")
try:
    response = requests.get("http://localhost:8000/health")
    print(f"Health status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Health endpoint failed: {e}")

# Test the query endpoint
print("\nTesting query endpoint...")
try:
    payload = {
        "query": "What is the main purpose of the Hybrid Book Index system?",
        "book_id": 1,
        "top_k": 10
    }
    response = requests.post("http://localhost:8000/query", json=payload)
    print(f"Query status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Query endpoint failed: {e}")

# Test the ToC endpoint
print("\nTesting ToC endpoint...")
try:
    response = requests.get("http://localhost:8000/books/1/toc")
    print(f"ToC status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"ToC endpoint failed: {e}")

print("\nEndpoint testing complete.")
from fastapi import FastAPI

app = FastAPI(
    title="Hybrid Book Index (HBI) System",
    description="API for indexing and querying book content.",
    version="0.1.0",
)

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    """
    return {"status": "ok"}

# The AI Agent's task is to build out the rest of the API endpoints here.
# For example: /ingest, /query, /books/{book_id}/toc
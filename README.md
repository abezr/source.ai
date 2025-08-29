# HBI (Hybrid Book Index) System

This project aims to build an enterprise-grade, observable, and governed system for indexing and querying PDF/DjVu books. The development is intended to be primarily executed by AI agents using the `opencode.ai` platform.

## Architecture

The system architecture is defined using the C4 model and can be found in `docs/architecture/system.dsl`. This is the single source of truth for the system's design.

## Local Development

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- `opencode.ai` CLI

### Setup
1.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Start all services using Docker Compose:
    ```bash
    docker-compose up -d
    ```

### Services
- **API:** `http://localhost:8000`
- **Grafana:** `http://localhost:3000`
- **Langfuse:** `http://localhost:3001`
- **MinIO Console:** `http://localhost:9001`

## AI-Native Development

This repository is configured for development with `opencode.ai`. The core instructions, agent definitions, and custom commands are defined in `AGENTS.md` and `opencode.json`.

To start a development session, simply run:
```bash
opencode
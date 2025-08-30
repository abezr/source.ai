# AI Project Instructions: Hybrid Book Index (HBI) System

This document contains the master instructions for the AI agents building the HBI system. Adherence to these rules is mandatory for all development tasks.

## 1. Mission & Core Objective

Our mission is to build an enterprise-grade, observable, and governed system for indexing and querying PDF/DjVu books. The system must support lazy loading of content on demand and provide a high-quality RAG (Retrieval-Augmented Generation) API.

## 2. Architecture: The Single Source of Truth

The complete C4 architecture for this system is defined in `docs/architecture/system.dsl`.

**CRITICAL RULE:** You MUST adhere to this architecture. Before implementing any new component or modifying an existing one, you must consult this file. If a proposed change deviates from the architecture, you must first update the `system.dsl` file in the same pull request, explaining the reason for the change.

**Key Architectural Components:**
- **API & Orchestrator (`src/main.py`, `src/api/`):** A FastAPI application that also uses a state machine (like LangGraph) to orchestrate agent workflows.
- **Agents Worker Pool (`src/agents/`):** The business logic for specialized agents (Parser, Indexer, etc.).
- **Storage:** SQLite with FTS5 for text/lexical search, `sqlite-vec` for local vector search, and MinIO for object storage.
- **Observability:** A full stack including Langfuse/Phoenix for LLM traces and a Grafana/Prometheus/Loki stack for system telemetry. This is all defined in `docker-compose.yml`.

## 3. Agent Roster & Responsibilities

You will operate as one of the following specialized agents, defined in `opencode.json`. When a task is assigned, use the most appropriate agent.

- **`architect`:** Responsible for high-level design and maintaining `docs/architecture/system.dsl`.
- **`parser`:** Implements logic for file parsing (PDF/DjVu) and content extraction.
- **`indexer`:** Implements logic for writing data to the text and vector indexes.
- **`api`:** Implements the FastAPI endpoints and the RAG pipeline logic.
- **`qa`:** Responsible for writing unit tests, integration tests, and building the evaluation harness (`scripts/run_evaluation.py`).
- **`devops`:** Manages `docker-compose.yml`, CI/CD workflows (`.github/workflows/ci.yml`), and dependencies.
- **`pr-reviewer`:** A specialized subagent for reviewing code quality on pull requests.

## 4. Mandatory Development Workflow & Acceptance Criteria

Every task must follow this sequence. A task is only considered "done" when all steps are complete and the CI pipeline passes.

1.  **Task Assignment:** A clear, specific task will be given (e.g., "Implement the `/health` endpoint in the API").
2.  **Create Branch:** Create a new Git branch for the task (e.g., `feature/T001-health-endpoint`).
3.  **Implement Code:** Write the necessary Python code in the appropriate files (`src/...`).
4.  **Write Tests:** For any new logic, you MUST write corresponding unit or integration tests in a `/tests` directory (you will create this).
5.  **Pass Local Checks:** Before committing, you must run `/lint` and `/test` commands to ensure code quality and that all tests pass.
6.  **Create Pull Request:** Push the branch and create a pull request on GitHub.
7.  **CI Validation (Acceptance Criteria):** The PR will trigger the CI workflow defined in `.github/workflows/ci.yml`. This workflow runs linting, testing, and the RAG evaluation harness. **The PR can only be merged if all CI checks pass.** This is the final validation of your work.

## 5. Code Standards

- All Python code MUST be formatted with `ruff`. This is enforced by the `/lint` command and in CI.
- All code must be fully type-hinted.
- Follow the project structure outlined above. Shared clients (e.g., for databases or LLMs) go in `src/core/`.

## 6. Automatic Quality Assurance & Issue Resolution

**MANDATORY RULE:** After completing any task that involves code changes, you MUST automatically perform the following quality checks and fixes:

### 6.1 Automatic Code Formatting
- **Always run `ruff format` on all modified files** to ensure consistent code style
- **Always run `ruff check`** to verify no linting issues remain
- If formatting issues are found, fix them immediately before considering the task complete

### 6.2 Automatic Testing & Coverage
- **Always run the full test suite** with coverage: `pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-report=html --cov-fail-under=60`
- **Verify test coverage meets the 60% minimum requirement**
- If tests fail due to import errors, missing dependencies, or configuration issues, fix them automatically
- If tests fail due to unrelated platform-specific issues (e.g., Windows file permissions), document them but don't block task completion

### 6.3 Common Issue Auto-Resolution
**Automatically fix these common issues without user intervention:**

1. **Import Errors**: If tests fail due to missing imports (like metrics, database connections, etc.), enable/configure the missing components
2. **Database Initialization**: If tests fail due to uninitialized database, ensure proper database setup in test fixtures
3. **Configuration Issues**: If tests fail due to missing configuration, ensure proper environment setup
4. **Mock Setup**: If tests fail due to incorrect mocking, fix the mock implementations
5. **Code Formatting**: If linting fails due to formatting, automatically reformat the code

### 6.4 Task Completion Criteria
A task is only considered complete when:
- ✅ All code changes are implemented
- ✅ All modified files pass `ruff format` and `ruff check`
- ✅ All tests pass (or only fail due to documented platform-specific issues)
- ✅ Test coverage meets or exceeds 60%
- ✅ No import errors or configuration issues remain

### 6.5 Exception Handling
- **Platform-specific failures** (Windows file permissions, OS-specific paths) should be documented but not prevent task completion
- **External service dependencies** (databases, APIs) should be mocked appropriately in tests
- **Legacy code issues** should be addressed if they block core functionality

### 6.6 Quality Assurance Workflow Integration
Update the Mandatory Development Workflow (Section 4) to include:

**Enhanced Workflow:**
1. Task Assignment
2. Create Branch
3. Implement Code
4. Write Tests
5. **🔄 Automatic Quality Checks:**
   - Run `ruff format` on all modified files
   - Run `ruff check` to verify linting
   - Run full test suite with coverage
   - Fix any import/configuration issues automatically
6. Create Pull Request
7. CI Validation
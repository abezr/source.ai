workspace "Hybrid Book Index (HBI) System - Governed AI Development" "A C4 model for a production-grade RAG system built by AI agents, featuring full observability and SDLC quality gates." {

    !identifiers hierarchical

    model {
        user = person "Reader / Analyst" "Searches books, asks questions, and consumes content via the API."
        developer = person "Developer / MLE" "Builds, operates, and governs the system using the Ops Portal and CI/CD feedback."

        hbi = softwareSystem "HBI (Hybrid Book Index) System" "Ingests PDF/DjVu, extracts structure, performs hybrid RAG with lazy chapter expansion, and exposes a governed API & Ops Portal." {
            api = container "API & Orchestrator" "The primary entrypoint. Handles HTTP requests, orchestrates agent workflows, and exposes configuration knobs." "Python, FastAPI, LangGraph" "Container"
            portal = container "Ops Portal" "A single-pane-of-glass UI for developers to monitor agent runs, view quality metrics, and tune system parameters." "TypeScript, Next.js" "UI"
            workers = container "Agents Worker Pool" "A pool of background workers that execute the individual agent tasks (parsing, embedding, etc.)." "Python" "Container" {
                ingestor = component "Ingestor Agent" "Detects file type, validates, hashes, and enqueues files for processing." "Python" "Agent"
                structureAgent = component "Structure Agent" "Extracts and normalizes the Table of Contents and other structural elements." "Python" "Agent"
                indexParser = component "Index Parser Agent" "Specifically parses the alphabetical index, handling complex formats like dotted leaders." "Python" "Agent"
                chunkerEmbedder = component "Chunker & Embedder Agent" "Performs semantic chunking and creates vector embeddings lazily on demand." "Python, FastEmbed" "Agent"
                ragRouter = component "RAG Router Agent" "Performs hybrid retrieval (lexical + vector), reranks results, and manages the lazy-loading window." "Python" "Agent"
                answerer = component "Answerer Agent" "Synthesizes the final answer from retrieved context, ensures mandatory citations, and applies confidence gates." "Python" "Agent"
                evaluator = component "Evaluator Agent" "Runs RAG evaluation suites (e.g., Ragas) and posts scores back to observability platforms." "Python, Ragas" "Agent"
                prReviewer = component "PR Reviewer Agent (MCP)" "A Dev-AI agent that lints, suggests tests, and flags risks on pull requests within the CI pipeline." "Python, MCP" "Agent"
            }
            textIndex = container "Text & Lexical Index" "Stores document metadata, text chunks, and a full-text search (FTS5) index." "SQLite (FTS5)" "Database"
            vectorIndex = container "Vector Index" "Stores vector embeddings for semantic search. Starts local, can mirror to a dedicated service." "sqlite-vec" "Database"
            objectStore = container "Object Storage" "Stores the original source books, page thumbnails, and other large binary artifacts." "MinIO (S3-compatible)" "Storage"
        }

        llmObservability = softwareSystem "LLM Observability Platform" "e.g., Langfuse or Arize Phoenix. Provides detailed tracing of LLM calls, cost/token tracking, and evaluation score visualization." "Observability"
        grafanaStack = softwareSystem "Infrastructure Observability Stack" "The classic Grafana, Prometheus, Loki, and Tempo stack for system metrics, logs, and traces, fed by an OpenTelemetry Collector." "Observability"
        sdlcQualitySuite = softwareSystem "SDLC Quality Suite" "Tools for automated quality gates and reporting, such as SonarQube, Codecov, and Allure." "SDLC"
        ciRunner = softwareSystem "CI/CD Runner" "e.g., GitHub Actions. Executes the build, test, evaluation, and deployment pipeline." "SDLC"
        hostedLLM = softwareSystem "Hosted LLM API" "Primary LLM provider for high-quality generation, e.g., Gemini 2.5 Pro." "LLM"
        localLLM = softwareSystem "Local LLM Fallback" "A locally-run model for cost-saving or offline capability, e.g., Ollama with Llama 3." "LLM"
        externalVectorDB = softwareSystem "External Vector DB" "A scalable, production-grade vector database for when the system grows, e.g., Qdrant." "VectorDB"

        user -> hbi.api "Sends queries, ingests documents"
        developer -> hbi.portal "Monitors system, tunes parameters, reviews agent activity"
        developer -> ciRunner "Reviews PRs with agent feedback"
        hbi.api -> hbi.workers "Dispatches and orchestrates agent tasks"
        hbi.api -> hbi.textIndex "Reads metadata and search results"
        hbi.api -> hbi.vectorIndex "Performs semantic search"
        hbi.api -> hbi.objectStore "Retrieves source files"
        hbi.workers -> hbi.textIndex "Writes structured data and text chunks"
        hbi.workers -> hbi.vectorIndex "Writes vector embeddings"
        hbi.workers -> hbi.objectStore "Writes page thumbnails and artifacts"
        hbi -> hostedLLM "Makes primary API calls"
        hbi -> localLLM "Uses as fallback or for specific tasks"
        hbi.vectorIndex -> externalVectorDB "Mirrors embeddings (optional)"
        hbi -> llmObservability "Sends detailed LLM traces, evals, and agent run data"
        hbi -> grafanaStack "Sends infrastructure metrics, logs, and traces via OpenTelemetry"
        hbi.portal -> llmObservability "Embeds trace views"
        hbi.portal -> grafanaStack "Embeds dashboards"
        hbi.portal -> sdlcQualitySuite "Shows Quality Gate status and links to reports"
        ciRunner -> hbi.workers.prReviewer "Triggers PR Reviewer Agent"
        ciRunner -> hbi.workers.evaluator "Runs evaluation suites"
        ciRunner -> sdlcQualitySuite "Publishes analysis, coverage, and test reports"

        deploymentEnvironment "Local Dev" {
            deploymentNode "Developer Machine" "" "Docker Desktop" {
                deploymentNode "HBI Services" {
                    containerInstance hbi.api
                    containerInstance hbi.portal
                    containerInstance hbi.workers
                    containerInstance hbi.textIndex
                    containerInstance hbi.vectorIndex
                    containerInstance hbi.objectStore
                }
                deploymentNode "Observability Services" {
                    softwareSystemInstance llmObservability
                    softwareSystemInstance grafanaStack
                }
                deploymentNode "Optional Services" {
                    softwareSystemInstance localLLM
                    softwareSystemInstance externalVectorDB
                }
            }
        }
    }

    views {
        systemContext hbi "C1_SystemContext" "The System Context diagram showing HBI as a black box and its key interactions." {
            include *
            autoLayout
        }

        container hbi "C2_Containers" "The Container diagram showing the major building blocks of the HBI system." {
            include *
            autoLayout
        }

        component hbi.workers "C3_Components_Agents" "The Component diagram zooming into the Agents Worker Pool to show the individual, specialized agents." {
            include *
            autoLayout
        }

        deployment hbi "Local Dev" "C4_Deployment_LocalDev" "The Deployment diagram showing how the entire system and its dependencies run on a local developer machine using Docker." {
            include *
            autoLayout
        }

        styles {
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "UI" {
                background #6f42c1
                color #ffffff
            }
            element "Component" {
                background #85bce0
                color #000000
            }
            element "Database" {
                shape Cylinder
                background #2a9d8f
                color #ffffff
            }
            element "Storage" {
                shape Folder
                background #2a9d8f
                color #ffffff
            }
            element "Agent" {
                shape Hexagon
                background #264653
                color #ffffff
            }
            element "Observability" {
                background #ffb703
                color #000000
            }
            element "SDLC" {
                background #e76f51
                color #ffffff
            }
            element "LLM" {
                background #118ab2
                color #ffffff
            }
            element "VectorDB" {
                background #4cc9f0
                color #000000
            }
        }
    }
}
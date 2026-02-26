# LexChat UK - Project Specification

## 1. Executive Summary
LexChat UK is a specialized, locally-hosted AI coding assistant designed for UK government legal departments. It leverages a Manager-Worker agent architecture to provide precise, legally-grounded answers to queries about UK legislation and case law. The system prioritizes data privacy (local hosting), accuracy (RAG + LEX API), and continuous improvement (Few-Shot Learning via user feedback).

## 2. Core Architecture

### 2.1 Technology Stack
-   **Frontend**: React 19 (Vite), served via Nginx (Alpine).
-   **Backend**: Python (FastAPI), PostgreSQL (Data persistence).
-   **AI Core**: Ollama (Local LLM inference), `google-sr` (Web Search).
-   **External Data**: LEX API (Authoritative legal text).
-   **Deployment**: Native Windows Installation.

### 2.2 Manager-Worker Agent System
Most legal queries require a multi-step approach. LexChat separates concerns:
1.  **Manager Agent**:
    -   **Role**: Interface layer.
    -   **Responsibility**: Maintains conversation context, triages user intent, and delegates "hard" legal questions to the Worker.
    -   **Tone**: Professional, objective, concise.
2.  **Worker Agent**:
    -   **Role**: Research specialist.
    -   **Responsibility**: Executes iterative research loops (Search -> Read -> Analyze) using `delegate_research` tools.
    -   **Constraint**: Ephemeral context (reset per query) to prevent hallucinations. Must cite sources.

## 3. Key Features

### 3.1 Legal Research Engine
-   **Deep Research**: Iterative web scraping and analysis for complex topics.
-   **LEX API Integration**: Direct retrieval of statutes and judgments.
-   **Strict Citation**: All answers must include URLs to `legislation.gov.uk` or official case law repositories.

### 3.2 Self-Improvement (Learning Mode)
-   **Feedback Loop**: Users rate answers (1-5 stars) and add comments.
-   **RAG Injection**:
    -   **Positive Memory**: High-rated Q&A pairs are injected as "Gold Standard" examples for similar future queries.
    -   **Negative Memory**: Low-rated comments are injected as "Warnings" to avoid repeating mistakes.

### 3.3 Security & Administration
-   **Auth**: JWT-based authentication with bcrypt password hashing.
-   **Admin Portal**:
    -   User management.
    -   **Usage Analytics**: Visual graphs of token consumption and query volume.
    -   **Learning Monitor**: View and manage user feedback/memories.

## 4. Deployment & Infrastructure
-   **Target Environment**: Windows Server 2022 (Air-gapped or restricted internet access).
-   **Automation**: PowerShell scripts (`install_native_offline.ps1`) for one-click deployment.

## 5. Future Roadmap
-   **Local RAG ingestion**: Ability to upload internal PDFs/Docs.
-   **Barrister Agent**: A third tier for specialized court strategy.
-   **Voice Mode**: Speech-to-text input.

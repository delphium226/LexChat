# LexChat UK - Legal Research Assistant

A locally hosted AI chatbot for UK legislation and case law research, powered by Ollama and the LEX API. This application uses a sophisticated **Manager-Worker Agent Architecture** to handle complex legal queries with precision and depth.

## Key Features

-   **🤖 Manager-Worker Architecture**:
    -   **Manager Agent**: Maintains conversation context and interacts with the user.
    -   **Worker Agent**: Performs deep, iterative research in an ephemeral context to prevent context window overflow and hallucinations.
-   **🔍 Deep Research**: Capable of performing iterative web searches (using `google-sr` and `cheerio`) to find specific legislation and case law.
-   **⚖️ LEX API Integration**: Connects to a specialized legal data API for authoritative UK statute and case law text.
-   **👮 Admin Portal**: Built-in system for managing users and viewing detailed **Usage Statistics** (token consumption, query counts) with interactive graphs and time-frame filtering.
-   **🔐 Authentication**: Secure signup and login functionality using JWT and bcrypt.
-   **📧 Email Integration**: Configured to send system notifications (requires SMTP credentials).
-   **🌓 Dark Mode**: Fully supported UI with a toggle for user preference.
-   **📝 Self-Improvement Loop**: A feedback mechanism where user ratings and comments (1-5 stars) are used to train the system via Few-Shot Learning (RAG), checking for past "Gold Standard" answers or "Critiques" before responding.

## Architecture

The application follows a modern client-server architecture:

### Frontend (Client)
-   **Framework**: React 19 (Vite)
-   **Styling**: Tailwind CSS
-   **Features**:
    -   Responsive Chat Interface
    -   Markdown Rendering with Citation Links
    -   Admin Dashboard (`/admin`)
    -   Settings & Profile Management

### Backend (Server)
-   **Runtime**: Python with FastAPI
-   **Database**: PostgreSQL
-   **AI Engine**: Ollama (Running locally)
-   **Responsibilities**:
    -   Agent Orchestration (Manager/Worker logic)
    -   Authentication & Session Management
    -   Prompt Engineering & Context Management

    -   Prompt Engineering & Context Management
    -   **Learning Module**: Retrieval of relevant past examples/critiques for context injection.

## Self-Improvement Loop

The application implements a unique **"Learning"** mechanism to get smarter over time without fine-tuning:

1.  **Data Collection**: Users rate responses (1-5 stars) and optionally leave comments.
2.  **Positive Reinforcement**: When a new query arrives, the system searches for past **similar queries** with **High Ratings (≥4)**. It injects these Q&A pairs into the context as "Gold Standard" examples.
3.  **Negative Reinforcement**: If past similar queries had **Low Ratings (≤3)** and comments, the system injects the *comment* as a "Warning/Critique" to prevent repeating the mistake.

## Admin Dashboard

The Admin Portal (`/admin`) provides comprehensive oversight of the application:

### 📊 Usage Analytics
-   **Interactive Graphs**: Visualise daily token usage and query volume using Recharts.
-   **Time-frame Filtering**: Filter data by last 7, 30, or 90 days (or all time) to spot trends.
-   **Cost Monitoring**: Track total input/output tokens to estimate LLM costs.

### 🧠 Learning Monitor
-   **Feedback Table**: View all user ratings and comments in real-time.
-   **Retrieval Playground**: Test the "Learning" logic by typing a query (e.g., "Duty of Care") to see exactly what "Memories" (Examples or Critiques) the agent retrieves for that topic.


## Native Windows Deployment (No Docker/WSL)

For environments where Docker or WSL are not available, you can run the application natively on Windows Server.

### Automated Setup
1.  Open PowerShell as Administrator.
2.  Run the installer:
    ```powershell
    cd deployment
    .\install_native_offline.ps1
    ```
3.  Start the application:
    ```cmd
    deployment\start_native.cmd
    ```
    *The application will be served securely over HTTPS on **port 443** (e.g., `https://localhost`).*

See [deployment/NATIVE_DEPLOYMENT.md](deployment/NATIVE_DEPLOYMENT.md) for full details.

## Offline (Air-Gapped) Windows Deployment

If deploying to a secure, internet-disconnected environment, use our offline native deployment scripts.

1. **Package Assets (Online)**: On an internet-connected machine, run `deployment\package_offline_native.ps1`. This downloads installers (Python, Postgres, Ollama), wheels, and pre-builds the frontend into `binaries\raw`.
2. **Chunk (Online)**: Run `deployment\compress_and_chunk.ps1` to zip all files and chunk them into `<50MB` parts for transfer.
3. **Reconstruct (Offline)**: Move the chunks to the target server and run `deployment\reconstruct_binaries.ps1` to stitch them back together into `binaries\raw`.
4. **Install (Offline)**: Run `deployment\install_native_offline.ps1` as Administrator to silently install all dependencies from the packaged binaries. You can append the `-SkipSystemInstall` flag to bypass reinstalling Python, Postgres, and Ollama.
5. **Start Application**: Run `deployment\start_native_offline.cmd` completely offline! The application will automatically open in your browser at `http://localhost:8080/`.

## Prerequisites (Local Development)

Before running the application locally (without Docker), ensure you have the following installed:

1.  **Node.js** (v18 or higher)
2.  **PostgreSQL** (v14 or higher)
3.  **Ollama** (v0.3 or higher)
    -   Ensure your Ollama instance is running.
    -   Pull the required models (e.g., `mistral-large`, `deepseek-v3`).

## Installation & Setup (Local Development)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd LexAPITest
```

### 2. Database Setup
The application is designed to **automatically initialize** the database schema on the first run.
-   Ensure your PostgreSQL service is running.
-   Create a database (e.g., `lexchat_db`):
    ```sql
    CREATE DATABASE lexchat_db;
    ```
-   The application will create the `users`, `chats`, and `messages` tables automatically.
-   **Default Admin**: On first run, a default admin account is created:
    -   **Username**: `admin`
    -   **Password**: `admin`

### 3. Environment Configuration
Create a `.env` file in the `server_py` directory with the following variables:

```env
# Server Configuration
PORT=8000
DATABASE_URL=postgresql://user:password@localhost:5432/lexchat_db

# Security
JWT_SECRET=your_super_secret_jwt_key

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434

# External APIs
LEX_API_URL=https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io

# Email (Optional)
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password
```

### 4. Install Dependencies

**Server:**
```bash
cd server_py
pip install -r requirements.txt
```

**Client:**
```bash
cd ../client
npm install
```

## Running the Application (Local Development)

### Start the Backend
```bash
cd server_py
uvicorn src.main:app --reload --port 8000
```
*The server runs on `http://localhost:8000`.*

### Start the Frontend
```bash
cd client
npm run dev
```
*The client runs on `http://localhost:5173` (typically).*

## Usage

1.  **Login/Signup**: Create a new account or log in with the default `admin` credentials (admin/admin).
2.  **Select Model**: Choose your preferred local LLM from the dropdown.
3.  **Ask a Question**: Type a legal query (e.g., *"What are the requirements for a Section 21 notice?"*).
4.  **Deep Research**: For complex topics, the system will automatically delegate to the Worker Agent to perform deep research steps.
5.  **Admin Portal**: Log in as `admin` and navigate to the Admin Portal to manage users.

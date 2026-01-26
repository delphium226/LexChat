# LexChat UK - Legal Research Assistant

A locally hosted AI chatbot for UK legislation and case law research, powered by Ollama and the LEX API. This application uses a sophisticated **Manager-Worker Agent Architecture** to handle complex legal queries with precision and depth.

## Key Features

-   **🤖 Manager-Worker Architecture**:
    -   **Manager Agent**: Maintains conversation context and interacts with the user.
    -   **Worker Agent**: Performs deep, iterative research in an ephemeral context to prevent context window overflow and hallucinations.
-   **🔍 Deep Research**: Capable of performing iterative web searches (using `google-sr` and `cheerio`) to find specific legislation and case law.
-   **⚖️ LEX API Integration**: Connects to a specialized legal data API for authoritative UK statute and case law text.
-   **👮 Admin Portal**: Built-in user management system allowing admins to view users via a secure dashboard.
-   **🔐 Authentication**: Secure signup and login functionality using JWT and bcrypt.
-   **📧 Email Integration**: Configured to send system notifications (requires SMTP credentials).
-   **🌓 Dark Mode**: Fully supported UI with a toggle for user preference.
-   **📝 Feedback System**: Users can rate and comment on AI responses to improve system performance over time.

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
-   **Runtime**: Node.js with Express
-   **Database**: PostgreSQL
-   **AI Engine**: Ollama (Running locally)
-   **Responsibilities**:
    -   Agent Orchestration (Manager/Worker logic)
    -   Authentication & Session Management
    -   Prompt Engineering & Context Management

## Docker Setup (Recommended)

You can run the entire application stack (Frontend, Backend, Database, and Ollama) using Docker.

### Prerequisites
- Docker Desktop installed and running.

### Quick Start
1. Run the automated setup script (PowerShell):
   ```powershell
   .\rebuild_docker.ps1
   ```
   This script will:
   - Tear down any existing containers.
   - Build the application images.
   - Start the database, Ollama, and the application.
   - Automatically trigger the download of required LLM models.

2. Access the application at `http://localhost:80` (or just `http://localhost`).

### Cloud Models & Authentication
If you are using cloud-hosted Ollama models (ending in `:cloud`), authentication is required.
The `docker-compose.yml` is configured to:
1.  Mount your local Ollama keys (`~/.ollama/id_ed25519`) into the container.
2.  Set the `OLLAMA_API_KEY` environment variable.

**Ensure you have authenticated locally first** if you regenerate your keys:
1. Run the key generation script:
   ```cmd
   .\gen_keys.cmd
   ```
2. Add the new public key (found in `ollama_auth/id_ed25519.pub`) to your [Ollama Dashboard](https://ollama.com/settings/keys).

### Manual Docker Commands
If you prefer running commands manually:
```bash
docker-compose up --build -d
```

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
Create a `.env` file in the `server` directory with the following variables:

```env
# Server Configuration
PORT=3000
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
cd server
npm install
```

**Client:**
```bash
cd ../client
npm install
```

## Running the Application (Local Development)

### Start the Backend
```bash
cd server
npm start
```
*The server runs on `http://localhost:3000`.*

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

# Native Windows Deployment Guide

This guide explains how to run LexChat natively on Windows Server 2022 without using Docker or WSL.

## Quick Start

We provide automated scripts to handle the entire process.

### 1. Installation
Run the installer script as Administrator. This will install Python, Node.js, PostgreSQL, Ollama, and set up the application.

```powershell
# Open PowerShell as Administrator
cd deployment
.\install_native.ps1
```

### 2. Running the App
Use the launcher script to start both the Backend and Frontend.

```cmd
deployment\start_native.cmd
```
*   **Frontend**: http://localhost:3000
*   **Backend**: http://localhost:8000

### 3. Updating
To pull the latest code and update dependencies:

```powershell
cd deployment
.\update_native.ps1
```

---

## Manual Setup Details

If you cannot use the automated scripts, here is what they do:

1.  **Dependencies**:
    *   Python 3.11+
    *   Node.js 20+ (LTS)
    *   PostgreSQL 15+ (User: `lexuser`, Pass: `lexpassword`, DB: `lexchat`)
    *   Ollama (Model: `mistral-large`)

2.  **Configuration**:
    *   The app uses a `.env.native` file in `server_py/` to configure `localhost` connections instead of Docker container names.

3.  **Build**:
    *   Backend: Standard `pip install -r requirements.txt` in a venv.
    *   Frontend: `npm run build` to generate static files.

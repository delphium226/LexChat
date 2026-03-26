# Native Windows Deployment Guide

This guide explains how to run LexChat natively on Windows Server 2022 without using Docker or WSL.

## Quick Start

We provide automated scripts to handle the entire process.

### 1. Installation
> [!WARNING]
> This native installer requires an **active internet connection** to download dependencies (Chocolatey, Node, Python, Postgres). If you are deploying to a secure, air-gapped environment without internet access, you **must use the Docker Offline Setup** instead (see `deployment\load_docker_offline.ps1`).

Run the installer script as Administrator. This will install Python, Node.js, PostgreSQL, Ollama, and set up the application.

```powershell
# Open PowerShell as Administrator
cd deployment
.\install_native.ps1
```

### 2. Configure SSL Certificates
To run the native environment over HTTPS, place your organizational security certificate files inside a `certs` directory within the `deployment` folder.
*   **Certificate file**: Save as `deployment\certs\lexchat.crt` (or `.pem`).
*   **Private key file**: Save as `deployment\certs\lexchat.key`.

### 3. Running the App
Use the launcher script to start the application natively.

```cmd
deployment\start_native.cmd
```
*   **Application URL**: https://localhost
*   *Note: If testing on an internal network, access the app via your machine's FQDN or hostname (e.g. `https://your-server-name`), matching the certificate.*

### 4. Updating
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

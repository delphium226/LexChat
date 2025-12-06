# LexChat UK - Legal Research Assistant

A locally hosted AI chatbot for UK legislation and case law research, powered by Ollama and the LEX API.

## Architecture

The application follows a modern client-server architecture designed to keep sensitive data within your local network while leveraging external legal databases.

### Frontend (Client)
- **Framework**: React (Vite)
- **Styling**: Tailwind CSS
- **Role**: Provides the chat interface, renders markdown responses, and manages user interaction. It communicates solely with the local backend server.

### Backend (Server)
- **Runtime**: Node.js with Express
- **Role**: Acts as the orchestrator between the user, the LLM (Ollama), and external data sources.
- **Agentic Logic**:
  - Receives user messages.
  - Forwards them to the local **Ollama** instance.
  - If the LLM requests it, the server executes "tools" to fetch real-world legal data.

### Integrations
- **Ollama (Local)**: Runs the Local Large Language Model (LLM) that powers the reasoning and conversation. All prompt processing happens here.
- **LEX API (External)**: A specialized API used by the backend to fetch real-time UK legislation and case law data. This data is fed back to the LLM to ground its answers in fact.

## Prerequisites
- **Ollama**: Must be running (configured for `http://192.168.1.221:11434`).
- **Node.js**: Installed on your machine.

## Setup & Run

### 1. Start the Backend
The backend handles the connection to Ollama and the LEX API.

```bash
cd server
npm install  # (If not already installed)
npm start
```
Server runs on `http://localhost:3000`.

### 2. Start the Frontend
The frontend provides the chat interface.

```bash
cd client
npm install  # (If not already installed)
npm run dev
```
Open your browser to the URL shown (usually `http://localhost:5173`).

## Features
- **Model Selection**: Choose any model available on your Ollama instance.
- **Legislation Search**: Finds Acts and Statutory Instruments.
- **Case Law Search**: Finds relevant court judgments.
- **Full Text**: Retrieves full text of legislation for the AI to analyze.
- **Privacy**: All AI processing happens on your local/network Ollama instance.

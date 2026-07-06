@echo off
mkdir ollama_auth 2>nul
ssh-keygen -t ed25519 -f ollama_auth/id_ed25519 -N "" -C "lexchat-key"
if %errorlevel% neq 0 (
    echo Key generation failed.
    exit /b %errorlevel%
)
echo Key pair generated successfully.

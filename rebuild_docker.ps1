# Check for Ollama keys
$ollamaPath = [System.IO.Path]::Combine($PWD, "ollama_auth", "id_ed25519")
if (-not (Test-Path $ollamaPath)) {
    Write-Warning "Ollama authentication keys not found at $ollamaPath"
    Write-Warning "You may need to run 'ollama signin' locally first, or cloud models will fail to authenticate."
    Write-Warning "Proceeding anyway..."
    Start-Sleep -Seconds 3
}

# Stop and remove containers, networks, images, and volumes
Write-Host "Tearing down existing Docker setup..."
docker-compose down --rmi local --volumes

# Build and start the containers
Write-Host "Building and starting Docker containers..."
docker-compose up --build -d

Write-Host "Application is starting at http://localhost:80"
Write-Host "Ollama models are being pulled in the background. Check logs for 'ollama-puller' if needed."

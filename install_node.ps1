[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$nodeDir = "C:\Users\rhett\node_portable"
$zip = "$nodeDir\node.zip"
$url = "https://nodejs.org/dist/v22.15.0/node-v22.15.0-win-x64.zip"

New-Item -ItemType Directory -Force -Path $nodeDir | Out-Null
Write-Host "Downloading Node.js v22 portable..."
curl.exe -L -o $zip $url
Write-Host "Extracting..."
Expand-Archive -Path $zip -DestinationPath $nodeDir -Force
Remove-Item $zip
Write-Host "Done. Node available at $nodeDir\node-v22.15.0-win-x64"

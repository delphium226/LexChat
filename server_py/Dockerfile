# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for some python packages like asyncpg build or others)
# For now, slim should suffice, but we might need build-essential if wheels aren't pre-built
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage cache
COPY server_py/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server_py/ .

# Copy frontend build (assuming it exists in client/dist from host)
# We place it in /app/client/dist so relative path "../client/dist" from /app (server root) 
# would imply /client/dist. 
# Our main.py logic checks /app/client/dist specifically now.
COPY client/dist /app/client/dist

# Expose port (Internal 8000)
EXPOSE 8000

# Run uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM node:18-alpine

WORKDIR /app

# Copy package.json and install dependencies
COPY server/package.json .
COPY server/package-lock.json* ./
RUN npm install

# Copy server source code
COPY server/src ./src
COPY server/.env* ./

# Copy client build to serve static files
COPY client/dist ../client/dist

# Expose port (default 3000)
EXPOSE 3000

# Start server
CMD ["node", "src/index.js"]

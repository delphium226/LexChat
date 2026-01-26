# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/client
COPY client/package*.json ./
RUN npm install
COPY client/ ./
RUN npm run build

# Stage 2: Setup the Node.js backend
FROM node:20-slim
WORKDIR /app/server
COPY server/package*.json ./
RUN npm install --production
COPY server/ ./

# Copy the built frontend from Stage 1
COPY --from=frontend-builder /app/client/dist ../client/dist

# Expose the server port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]

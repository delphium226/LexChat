
# Stage 1: Build React App
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Copy the nginx.conf from the build context (which will be the project root, so we need to adjust path in compose or copy it here if context is client specific)
# Actually, standard practice is to COPY strict confs.
# We will mount it in docker-compose or copy it. Let's assume we copy it from root context if we run from root.
# But this Dockerfile is in client/, so context is typically client/.
# Let's rely on docker-compose to mount the nginx.conf, OR copy a default one.
# For now, we will rely on docker-compose mounting the conf, or we can copy it if we pass it in context.
# To be safe and self-contained, let's just use the default nginx and let mount handle it, 
# OR we can assume the build context is the root.
# Let's assume the build context will be the project root in docker-compose.
# Wait, standard `docker build` usually expects context.
# Let's keep it simple: We will mount nginx.conf in docker-compose.
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

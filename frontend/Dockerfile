# Stage 1 — build React app
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install --frozen-lockfile || npm install
COPY . .
RUN npm run build

# Stage 2 — copy dist to a shared volume accessible by nginx
FROM alpine:3.19

RUN mkdir -p /dist
COPY --from=builder /app/dist /dist

# This container just holds the static files — nginx reads from the volume
CMD ["sh", "-c", "cp -r /dist/. /usr/share/nginx/html/ && echo 'Frontend assets copied' && tail -f /dev/null"]


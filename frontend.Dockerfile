FROM node:20-slim AS builder
WORKDIR /app
RUN npm i -g pnpm
COPY frontend-v3/package.json frontend-v3/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile
COPY frontend-v3/ ./
RUN pnpm build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]

# Frontend image for the optional Docker stack (`make up`): a static Vite
# build served by nginx, which also proxies /v1 to the backend container.
# For development, run `make frontend` natively instead.

FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build


FROM nginx:1.28-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=6 \
    CMD wget --quiet --spider http://127.0.0.1/ || exit 1

FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY vite.config.js index.html ./
COPY src ./src

RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html

# The nginx image auto-runs envsubst over /etc/nginx/templates/*.template
# at container start and writes results to /etc/nginx/conf.d/. Only vars
# listed in NGINX_ENVSUBST_FILTER_VARIABLES are substituted, so nginx's
# own $host / $remote_addr placeholders stay intact.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Runtime defaults; docker-compose can override.
ENV BACKEND_URL="http://backend:8000" \
    NGINX_ENVSUBST_FILTER_VARIABLES="BACKEND_URL"

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

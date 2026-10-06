# Étape 1 : build React
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
COPY . .
# URL du flux MJPEG du script ai/vision.py, vue depuis le navigateur du superviseur
ARG VITE_VIDEO_URL=http://localhost:8001/stream
ENV VITE_VIDEO_URL=$VITE_VIDEO_URL
RUN npm run build

# Étape 2 : nginx (le template est rendu avec envsubst au démarrage : API_KEY)
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx/conf.d
EXPOSE 80

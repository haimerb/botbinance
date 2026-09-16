FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

RUN adduser -D -H -h /var/cache/nginx -s /sbin/nologin nginxuser && \
    chown -R nginxuser:nginxuser /var/cache/nginx /var/run /var/log/nginx /usr/share/nginx/html && \
    chmod -R 755 /var/cache/nginx /var/run /var/log/nginx /usr/share/nginx/html

USER nginxuser

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
FROM node:22-alpine
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile --ignore-scripts
COPY . .
ENV CI=true
# NEXT_PUBLIC_* se hornea en el bundle del cliente durante el build, no se lee en
# runtime — por eso tiene que llegar como build ARG, no solo como env var del
# contenedor. Sin esto, el navegador siempre terminaba hablando con el proxy
# same-origin de next.config.js (/api -> api:8000) y el backend nunca veía la IP
# real del visitante, solo la del contenedor del dashboard.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN pnpm run build
CMD ["pnpm", "start"]

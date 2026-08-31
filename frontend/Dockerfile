# AutoScore frontend — Vite dev server (React + TS + Tailwind).
# For a production build, run `npm run build` and serve `dist/` with any static host.
FROM node:22-slim

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

EXPOSE 5173
# --host so the dev server is reachable from outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

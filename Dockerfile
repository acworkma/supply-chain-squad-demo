# Stage 1: Build React UI
FROM node:20-alpine AS ui-builder
WORKDIR /build
COPY src/ui/package*.json ./
RUN npm ci
COPY src/ui/ ./
RUN npm run build

# Stage 2: Python API + static files
FROM python:3.12-slim
WORKDIR /app

# Install Python dependencies first (cached layer — only rebuilds when deps change)
COPY src/api/pyproject.toml ./
RUN python3 -c "import tomllib; \
    deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; \
    open('/tmp/requirements.txt', 'w').write('\n'.join(deps))" && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application source
COPY src/api/ ./

# Copy UI build output to where FastAPI serves static files
COPY --from=ui-builder /build/dist ./static

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

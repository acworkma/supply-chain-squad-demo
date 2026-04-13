# Stage 1: Build React UI
FROM node:20-alpine AS ui-builder
WORKDIR /build
COPY src/ui/package*.json ./
RUN npm ci --legacy-peer-deps
COPY src/ui/ ./
RUN npm run build

# Stage 2: Install Python dependencies (build stage with compiler toolchain)
FROM mcr.microsoft.com/azurelinux/base/python:3.12 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN tdnf install -y gcc g++ libffi-devel && tdnf clean all

WORKDIR /app
COPY src/api/pyproject.toml ./
RUN python3 -c "import tomllib; \
    deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; \
    open('/tmp/requirements.txt', 'w').write('\n'.join(deps))" && \
    pip install --no-cache-dir --target=/app/deps -r /tmp/requirements.txt

# Stage 3: Minimal runtime (distroless — no shell, no package manager)
FROM mcr.microsoft.com/azurelinux/distroless/python:3.12-nonroot

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/deps

COPY --from=builder /app/deps /app/deps
COPY src/api/ ./
COPY --from=ui-builder /build/dist ./static

EXPOSE 8000

ENTRYPOINT ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

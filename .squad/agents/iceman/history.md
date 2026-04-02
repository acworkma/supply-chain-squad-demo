# Project Context

- **Owner:** acworkma
- **Project:** Patient Flow / Bed Management — Agentic AI Demo (Azure + Foundry + ACA)
- **Stack:** Python/FastAPI backend, React/Tailwind/shadcn frontend, Azure Container Apps, Azure AI Foundry, Bicep/azd infra
- **Created:** 2026-03-07

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-07: WI-004 — Azure Infra Scaffolding Complete

- **Files created:** `azure.yaml`, `Dockerfile`, `infra/main.bicep`, `infra/main.bicepparam`, `infra/modules/observability.bicep`, `infra/modules/foundry.bicep`, `infra/modules/aca.bicep`, `.github/workflows/deploy.yml`
- **AI Foundry Bicep pattern:** `Microsoft.CognitiveServices/accounts` (kind: AIServices) → `Microsoft.MachineLearningServices/workspaces` (kind: Hub, with connections sub-resource) → kind: Project (hubResourceId links to Hub). Model deployments go on the CognitiveServices account, not the ML workspace.
- **ACA managed identity RBAC:** System-assigned identity needs `AcrPull` scoped to ACR, and `Cognitive Services OpenAI User` scoped to AI Services account. Used well-known role definition GUIDs.
- **Container App config:** Single container, port 8000, min 0 / max 1 replicas, 0.5 CPU / 1Gi mem. Env vars: PROJECT_ENDPOINT, MODEL_DEPLOYMENT_NAME, APP_THEME=dark, APPLICATIONINSIGHTS_CONNECTION_STRING.
- **Dockerfile:** Two-stage — Node 20 alpine builds React UI, Python 3.12-slim runs FastAPI + serves static. Aligns with ADR-005.
- **CI/CD:** GitHub Actions with OIDC federated credentials for azd auth. Uses `Azure/setup-azd@v2`.
- **azd hooks:** `postprovision` runs `python scripts/build_agents.py` to create Foundry agents after infra is up.
- **Key decision:** Disabled local auth on AI Services (`disableLocalAuth: true`) to enforce Entra ID-only auth per spec.

### 2026-03-07: WI-019 — CI/CD Pipeline (lint + test for PRs)

- **File modified:** `.github/workflows/squad-ci.yml` — replaced generic Node.js test with proper dual-job pipeline
- **Backend job:** Python 3.12, `pip install -e ".[test]"`, ruff lint (non-blocking — 19 pre-existing issues), pytest 318 tests
- **Frontend job:** Node 22, `npm ci`, `npm run build` (tsc type-check + vite build)
- **Jobs run in parallel** — no dependencies between them
- **Ruff lint is `continue-on-error: true`** until team cleans up the 19 existing lint warnings. Remove the flag once clean.
- **Triggers:** PR to main + push to main. Deploy workflow (`deploy.yml`) left untouched.
- **Validated locally:** 318 pytest pass, ruff reports 19 fixable issues, frontend build succeeds

### 2026-03-09: WI-027 — Multi-Model Deployment (gpt-4.1, gpt-5-mini)

- **Files modified:** `infra/modules/foundry.bicep`, `infra/main.bicep`, `infra/main.bicepparam`
- **Refactor pattern:** Replaced single-model params (`modelName`, `modelVersion`, `modelCapacity`) with `modelDeployments` array parameter. Foundry module loops with `@batchSize(1)` to deploy sequentially (ARM provider requirement for deployments on the same account).
- **New deployments:** `gpt-4.1` (50K TPM, GlobalStandard), `gpt-5-mini` (50K TPM, GlobalStandard). Existing `gpt-5.2` (100K TPM) unchanged.
- **Primary model:** Retained `modelName` param (default `gpt-5.2`) passed through as `primaryModelName` so ACA's `MODEL_DEPLOYMENT_NAME` env var is unchanged. New `ALL_MODEL_DEPLOYMENT_NAMES` output exposes all deployment names for the eval harness.
- **Model versions:** Used reasonable defaults; added comments directing operators to verify with `az cognitiveservices model list --location <region>`.
- **Validation:** `az bicep build` passes clean. ARM template (`main.json`) regenerated.

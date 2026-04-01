# Squad Team

> Supply Chain Management — Agentic AI Demo (Azure + Foundry + ACA)

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Maverick | Lead | .squad/agents/maverick/charter.md | 🏗️ Lead |
| Goose | Backend Dev | .squad/agents/goose/charter.md | 🔧 Backend |
| Viper | Frontend Dev | .squad/agents/viper/charter.md | ⚛️ Frontend |
| Iceman | DevOps/Infra | .squad/agents/iceman/charter.md | ⚙️ DevOps |
| Jester | Tester | .squad/agents/jester/charter.md | 🧪 Tester |
| @copilot | Coding Agent | copilot-instructions.md | 🤖 Coding Agent |
| Scribe | Session Logger | .squad/agents/scribe/charter.md | 📋 Scribe |
| Ralph | Work Monitor | — | 🔄 Monitor |

## Coding Agent — @copilot

**Badge:** 🤖 Coding Agent
**Instructions:** `copilot-instructions.md` (repo root)
<!-- copilot-auto-assign: true -->

### Capabilities

| Category | Fit | Notes |
|----------|-----|-------|
| Bug fixes (well-defined, repro steps) | 🟢 | Good fit |
| Test writing (unit, integration) | 🟢 | Good fit |
| Small features (bounded scope, clear spec) | 🟢 | Good fit |
| Dependency updates | 🟢 | Good fit |
| Documentation updates | 🟢 | Good fit |
| API design / architecture decisions | 🔴 | Route to Maverick |
| Security-sensitive work (auth, encryption) | 🔴 | Route to squad member |
| Multi-file refactors (3+ files, design judgment) | 🟡 | Needs squad review |
| UI/UX work (visual design, layout) | 🟡 | Needs Viper review |
| Infra/Bicep changes | 🔴 | Route to Iceman |

## Issue Source

- **Repository:** acworkma/supply-chain-squad-demo
- **Connected:** 2026-04-01
- **Filters:** all open issues

## Project Context

- **Owner:** acworkma
- **Project:** Supply Chain Management — Agentic AI Demo
- **Stack:** Python/FastAPI, React/Tailwind/shadcn/ui, Azure Container Apps, Azure AI Foundry, Bicep/azd
- **Universe:** Top Gun (aviation)
- **Created:** 2026-04-01

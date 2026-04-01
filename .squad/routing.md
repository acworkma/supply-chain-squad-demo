# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Architecture, system design, agent design | Maverick | Component boundaries, API contracts, domain model design, agent roster design |
| Backend API, domain model, agent orchestration | Goose | FastAPI endpoints, state machines, event emission, build_agents.py, Foundry SDK |
| Frontend UI, components, styling | Viper | React components, Tailwind/shadcn, dark-mode layout, command center UI |
| Azure infra, provisioning, deployment | Iceman | Bicep, azd, ACA, ACR, Foundry resource/project, CI/CD, env vars |
| Code review | Maverick | Review PRs, architectural quality, API contract conformance |
| Testing, QA, scenarios | Jester | pytest, Vitest, scenario validation, smoke tests, edge cases |
| Scope & priorities | Maverick | What to build next, trade-offs, decisions |
| Async issue work (bugs, tests, small features) | @copilot 🤖 | Well-defined tasks matching capability profile |
| Session logging | Scribe | Automatic — never needs routing |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, evaluate @copilot fit, assign `squad:{member}` label | Lead |
| `squad:{name}` | Pick up issue and complete the work | Named member |
| `squad:copilot` | Assign to @copilot for autonomous work (if enabled) | @copilot 🤖 |

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.**
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member.
8. **@copilot routing** — check capability profile in `team.md` before routing.

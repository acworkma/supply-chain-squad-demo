# Meet the Squad

> The human team behind the demo — a crew of AI specialists that live in this repo and collaborate through the [`/squad`](https://github.com/bradygaster/squad) command.

Not to be confused with the five in-app supply-chain agents (Supply Coordinator, Supply Scanner, Catalog Sourcer, Order Manager, Compliance Gate) — those are the agents the **demo** runs. The squad documented on this page is the **development team** that builds and maintains the demo. Each squad member has a distinct role, a charter that governs what they own, and a preferred LLM chain.

## The Crew

Six agents, callsigns drawn from *Top Gun*. Scribe is silent and runs in the background; the other five do the visible work.

| Callsign | Role | What They Own |
|---|---|---|
| **Maverick** | Lead / Architect | System architecture, code review, scope & priority calls, agent system design, API contracts |
| **Goose** | Backend Developer | `src/api/` (FastAPI), domain state model, agent orchestration, `scripts/build_agents.py`, backend tests |
| **Viper** | Frontend Developer | `src/ui/` (React + TypeScript + Tailwind + shadcn/ui), three-pane control tower layout, dark-mode theming, real-time data display |
| **Iceman** | DevOps / Infrastructure | `infra/` (Bicep), `azure.yaml`, azd provisioning, ACA + ACR + Foundry + observability, CI/CD, runtime configuration |
| **Jester** | Tester / QA | Test strategy, pytest + Vitest suites, scenario validation, `scripts/smoke_test.sh`, edge-case analysis |
| **Scribe** | Session logger (background) | `.squad/log/`, `.squad/decisions.md`, cross-agent context propagation. Never speaks to the user — just remembers. |

Each member's full charter — voice, boundaries, collaboration rules — lives in `.squad/agents/<callsign>/charter.md`.

## How They Pick LLMs

Most agents use `Preferred: auto`. That means the Squad coordinator picks a model per task from tiered fallback chains defined in [`squad.config.ts`](../squad.config.ts), with a general rule of *cost-first unless writing code*.

**Default model:** `claude-sonnet-4.5` · **Default tier:** `standard`

### Fallback chains

| Tier | Chain |
|---|---|
| **premium** | `claude-opus-4.7` → `claude-opus-4.6` → `claude-opus-4.6-fast` → `claude-opus-4.5` → `claude-sonnet-4.5` |
| **standard** | `claude-sonnet-4.5` → `gpt-5.2-codex` → `claude-sonnet-4` → `gpt-5.2` |
| **fast** | `claude-haiku-4.5` → `gpt-5.1-codex-mini` → `gpt-4.1` → `gpt-5-mini` |

`preferSameProvider: true` is on, so when a model in a chain fails, the coordinator keeps walking the chain while staying within the same provider family where possible.

### Per-agent model assignments

| Agent | Preferred Model | Family | Rationale |
|---|---|---|---|
| Maverick | auto | — | Coordinator picks per task (usually a capable Anthropic model for architecture and review) |
| Goose | auto | — | Coordinator picks per task; code-generation tasks tend up the standard/premium Anthropic chain |
| Viper | auto | — | Coordinator picks per task; same pattern as Goose |
| Iceman | auto | — | Coordinator picks per task; infra changes lean toward cost-efficient tiers when not writing code |
| **Jester** | **`gpt-5.2-codex`** | **OpenAI** | **Pinned.** Tests should be authored by a different model family than the devs. Cross-provider authorship reduces the chance of model-specific blind spots slipping through. |
| Scribe | auto | — | Short, silent background work — usually falls to the fast tier |

Jester's pin is configured via `models.roleMapping` in [`squad.config.ts`](../squad.config.ts). With `preferSameProvider: true`, Jester's effective fallback chain is OpenAI-only:

`gpt-5.2-codex` → `gpt-5.2` → `gpt-5.1-codex-mini` → `gpt-4.1` → `gpt-5-mini`

## How the Squad Works Together

- **Routing** — Work types (`feature-dev`, `bug-fix`, `testing`, `documentation`) map to agents via `routing.rules` in `squad.config.ts`.
- **Decisions** — Any agent can record a cross-cutting decision by dropping a file in `.squad/decisions/inbox/`. Scribe merges into `.squad/decisions.md`, which every agent reads before starting work.
- **Reviews** — If one agent rejects another's work, the Coordinator assigns a *different* agent to revise — never the original author. This keeps blind spots from compounding.
- **Casting** — Squad members are cast from the *Top Gun* universe per `casting.allowlistUniverses` in the config. Future specialists may be drawn from The Usual Suspects, Breaking Bad, The Wire, or Firefly.

## Changing the Crew

- **Swap a model family for one agent:** add an entry under `models.roleMapping` in `squad.config.ts` and update that agent's charter `Model` section to document the rationale.
- **Update a fallback chain:** edit `models.fallbackChains.<tier>` in `squad.config.ts`. No charter changes needed unless an agent was pinned to a now-removed model.
- **Add a new squad member:** create `.squad/agents/<callsign>/charter.md` (use an existing charter as a template) and add a matching `AgentConfig` entry if you want structured routing.

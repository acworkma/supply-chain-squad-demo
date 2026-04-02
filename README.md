# Patient Flow & Bed Management — Agentic AI Demo

> **Six AI agents. One patient flow. Zero manual coordination.**

Every hospital knows the bottleneck: a patient needs a bed, and what follows is a cascade of phone calls, pages, and whiteboard updates across admissions, housekeeping, transport, and nursing. Beds sit empty while teams play phone tag. Patients wait in the ED for hours.

This demo shows a different approach. **Six AI agents work together in real time** to handle the entire bed placement workflow — from the moment a patient needs a bed to the moment they arrive in it. No human coordination required. Every decision, every handoff, every contingency is visible in a live Control Tower dashboard.

Built on [Microsoft Foundry](https://ai.azure.com/) and designed to run as a live, clickable demo.

## Meet the AI Team

Each agent has a specific job in the patient flow, just like real hospital staff:

| Agent | What They Do |
|-------|-------------|
| **Bed Coordinator Assistant** | The central hub of the AI team. Aggregates signals from all agents, surfaces placement recommendations, and drives the workflow end-to-end. Every other agent reports back through the Bed Coordinator Assistant. |
| **Predictive Capacity** | Looks at current bed availability, patient acuity, and unit fit to rank the best bed options. Thinks ahead — which beds are about to open? Which units are nearing capacity? |
| **Bed Allocation** | Handles the actual reservation. Once a bed is chosen, Bed Allocation locks it down so no one else can claim it. |
| **EVS Tasking** | The housekeeping dispatcher. If a bed needs cleaning or room prep before a patient can move in, EVS Tasking creates and tracks that work order. |
| **Transport Ops** | Schedules the patient's physical move — from current location to their assigned bed. Manages priority and dispatch. |
| **Policy & Safety** | The compliance check. Before any bed assignment is finalized, Policy & Safety validates it against isolation requirements, acuity rules, and safety constraints. Can block or escalate if something doesn't look right. |

## The Demo Scenarios

### ER Admission — Smooth Placement

A patient arrives in the ED needing admission. Watch the agents:

1. **Bed Coordinator Assistant** picks up the request and asks Predictive Capacity to rank available beds
2. **Predictive Capacity** scores and ranks the options
3. **Policy & Safety** validates the top choice — no safety concerns
4. **Bed Allocation** reserves the bed
5. **Transport Ops** dispatches a transport team
6. The patient moves through **Transport Ready → In Transit → Arrived**
7. Bed status flips to **Occupied**

The whole flow takes about 5 seconds. Every step is visible in the Agent Conversation panel.

### Disruption + Replan — When Things Go Wrong

Same scenario, but mid-workflow a bed gets **blocked** (water leak in the room). Watch the agents adapt:

1. The initial placement starts normally
2. **EVS Tasking** detects the blockage and **escalates** to the Bed Coordinator Assistant
3. **Policy & Safety** recommends a fallback bed
4. **Bed Allocation** releases the blocked reservation and secures the new bed
5. **Transport Ops** reschedules to the new destination
6. The patient still arrives — just at a different bed

This is the real showcase: **the agents don't just follow a script — they handle disruptions and replan on the fly.**

## Running the Demo

| Option | What You Need | Guide |
|--------|--------------|-------|
| **Local** | Python + Node.js (no Azure account required) | [Local setup guide](docs/local-development.md) |
| **Azure** | Azure subscription + `azd` CLI | [Azure deployment guide](docs/azure-deployment.md) |

Once it's running:

1. The **Control Tower** loads with a pre-set hospital — 16 beds across three units on two campuses
2. Use the **scenario dropdown** to select a demo:
   - **Admissions:** ER Admission or OR Admission (post-surgical)
   - **Disruptions:** Disruption + Replan or EVS-Gated Placement
   - **Transfers:** Unit Transfer
3. Click **"Reset"** between scenarios to restore the initial state
4. Watch the **left panel** (beds updating), **upper right** (agent conversation), and **lower right** (event timeline)

## Learn More

| Topic | Link |
|-------|------|
| Architecture & technical design | [docs/architecture.md](docs/architecture.md) |

## License

[MIT](LICENSE)

# Supply Closet Replenishment — Agentic AI Demo

> **Five AI agents. One supply chain. Zero manual coordination.**

Every hospital knows the bottleneck: a supply closet runs low, and what follows is a cascade of manual counts, phone calls, and paper forms across nursing, procurement, and receiving. Shelves sit empty while teams scramble. Patients wait for basic supplies.

This demo shows a different approach. **Five AI agents work together in real time** to handle the entire supply closet replenishment workflow — from detecting a low-stock item to confirming delivery. No human coordination required. Every decision, every handoff, every contingency is visible in a live Control Tower dashboard.

Built on [Microsoft Foundry](https://ai.azure.com/) and designed to run as a live, clickable demo.

## Meet the AI Team

Each agent has a specific job in the supply chain, just like real hospital staff:

| Agent | What They Do |
|-------|-------------|
| **Supply Coordinator** | The central hub of the AI team. Aggregates signals from all agents, surfaces replenishment recommendations, and drives the workflow end-to-end. Every other agent reports back through the Supply Coordinator. |
| **Supply Scanner** | Monitors current inventory levels, par levels, and consumption trends to identify items needing restock. Thinks ahead — which items are trending toward shortage? Which closets are nearing critical levels? |
| **Catalog Sourcer** | Finds the best sourcing options for needed items. Checks approved vendor catalogs, pricing, lead times, and contract status to recommend the optimal purchase. |
| **Order Manager** | Handles the actual purchase order lifecycle. Once a sourcing option is chosen, Order Manager creates the PO, tracks fulfillment, and confirms delivery. |
| **Compliance Gate** | The compliance check. Before any order is finalized, Compliance Gate validates it against formulary rules, budget limits, and regulatory constraints. Can block or escalate if something doesn't look right. |

## The Demo Scenarios

### Routine Restock — Smooth Replenishment

A supply closet's par levels trigger a restock request. Watch the agents:

1. **Supply Coordinator** picks up the request and asks Supply Scanner to assess inventory
2. **Supply Scanner** identifies items below par and ranks urgency
3. **Catalog Sourcer** finds optimal vendors and pricing
4. **Compliance Gate** validates the order — no policy concerns
5. **Order Manager** creates the purchase order and tracks delivery
6. Items move through **PO Created → Approved → Shipped → Delivered**
7. Inventory levels update to reflect restocked quantities

The whole flow takes about 5 seconds. Every step is visible in the Agent Conversation panel.

### Critical Shortage — When Things Go Urgent

Same workflow, but a supply item hits **critical** level (below safety stock). Watch the agents adapt:

1. The restock starts with elevated urgency
2. **Supply Scanner** flags the critical shortage and **escalates** to the Supply Coordinator
3. **Catalog Sourcer** searches for expedited sourcing options
4. **Compliance Gate** fast-tracks approval for emergency procurement
5. **Order Manager** creates an expedited PO with priority shipping
6. The item is restocked — with expedited handling throughout

This is the real showcase: **the agents don't just follow a script — they handle urgency levels and adapt their workflow accordingly.**

## Running the Demo

| Option | What You Need | Guide |
|--------|--------------|-------|
| **Local** | Python + Node.js (no Azure account required) | [Local setup guide](docs/local-development.md) |
| **Azure** | Azure subscription + `azd` CLI | [Azure deployment guide](docs/azure-deployment.md) |

Once it's running:

1. The **Control Tower** loads with a pre-set supply closet — items across multiple categories and vendors
2. Use the **scenario dropdown** to select a demo:
   - **Routine Restock:** Standard par-level replenishment
   - **Critical Shortage:** Expedited procurement for urgent items
3. Click **"Reset"** between scenarios to restore the initial state
4. Watch the **left panel** (inventory updating), **upper right** (agent conversation), and **lower right** (event timeline)

## Learn More

| Topic | Link |
|-------|------|
| Architecture & technical design | [docs/architecture.md](docs/architecture.md) |
| Meet the squad (the AI dev crew behind this repo) | [docs/squad.md](docs/squad.md) |

## License

[MIT](LICENSE)

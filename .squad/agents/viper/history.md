# Project Context

- **Owner:** acworkma
- **Project:** Patient Flow / Bed Management — Agentic AI Demo (Azure + Foundry + ACA)
- **Stack:** Python/FastAPI backend, React/Tailwind/shadcn frontend, Azure Container Apps, Azure AI Foundry, Bicep/azd infra
- **Created:** 2026-03-07

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-07: WI-005 — UI Shell Created

- **UI lives in `src/ui/`** — fully self-contained Vite + React + Tailwind + TypeScript project
- **Three-pane layout** via CSS Grid: left 55% (Ops Dashboard with stacked Patient Queue / Bed Board / Transport Queue), right 45% split vertically into Agent Conversation (55%) and Event Timeline (45%)
- **Color tokens** defined in `tailwind.config.ts` under `tower-*` namespace: bg, surface, border, accent (teal #06b6d4), warning (amber), success (green), error (red)
- **Component structure**: `components/layout/` (ControlTower, PaneHeader), `components/dashboard/` (PatientQueue, BedBoard, TransportQueue), `components/conversation/` (AgentConversation), `components/timeline/` (EventTimeline)
- **PaneHeader** is reusable: takes LucideIcon, title, optional badge with color variant. Includes subtle accent gradient bar at top.
- **`cn()` utility** in `src/lib/utils.ts` — standard clsx + tailwind-merge pattern for conditional class merging
- **Vite proxy**: `/api` → `http://localhost:8000` configured for dev — aligns with ADR-005 (single container in prod, split dev servers)
- **Path alias**: `@/*` → `./src/*` set in both tsconfig.app.json and vite.config.ts
- **Dark mode only** — `class="dark"` on `<html>`, custom scrollbar styles, `color-scheme: dark`
- Build verified clean, dev server confirmed serving on :5173

### 2026-03-07: WI-010/011/012 — Phase 2 Frontend — Real Data Panes

- **New shared infra created**: `types/api.ts` (all TS interfaces/unions mirroring backend Pydantic models), `lib/colors.ts` (color mapping functions for every state enum), `hooks/useApi.ts` (polls /api/state every 2s), `hooks/useSSE.ts` (generic SSE hook with auto-reconnect)
- **ControlTower** now owns data: calls `useApi()` + `useSSE()`, passes typed props to all child components. PaneHeader badges show live counts.
- **PatientQueue** — sortable table (acuity-first, then wait time). Color-coded state badges, monospace MRN/wait/acuity. Handles loading/error/empty states.
- **BedBoard** — compact grid grouped by unit. Each card shows room+bed letter, state dot + label, patient name or reserved indicator. Ring highlight for reservations.
- **TransportQueue** — row list with priority badge, patient→destination route, state, scheduled time.
- **AgentConversation** — chat transcript with per-agent avatar colors (keyword-matched: flow=blue, predictive=purple, bed=green, evs=amber, transport=cyan, policy=red). Intent tag badges, related event ID chips, auto-scroll.
- **EventTimeline** — append-only log with expand-to-reveal payload JSON + state diff (from→to). Event type color-coded by domain. Monospace sequence/timestamp. Auto-scroll.
- **Design discipline**: zero new dependencies installed. All styling via Tailwind utility classes + tower-\* tokens. Transition-colors on hover/state changes. Monospace for data fields.
- Build verified clean (tsc --noEmit + vite build).

### 2026-03-07: WI-017 — Frontend ↔ API Integration (SSE + Scenario Triggers)

- **`useSSE` hook enhanced** — now returns `{ items: T[], connected: boolean }` instead of plain `T[]`. Tracks `onopen` for connected state, `onerror` for disconnected. All consumers updated to destructure.
- **`ScenarioToolbar` component created** at `components/layout/ScenarioToolbar.tsx` — contains scenario trigger buttons (Happy Path, Disruption + Replan, Reset), scenario running status with ping animation, and connection status indicator.
- **Scenario trigger pattern**: POST to `/api/scenario/*`, disable all buttons while triggering, 30s auto-clear on running status. Reset clears scenario status immediately.
- **Connection status**: OR of both SSE streams (events + messages). Green dot = Connected, red dot = Disconnected. Uses `Radio` icon from lucide-react.
- **ControlTower layout changed** — outer div is now `flex flex-col` with toolbar in a fixed top row and the grid panes in `flex-1`. No height changes to pane layout.
- **Design consistency**: All new elements use tower-\* tokens, dark-mode-only, subtle border/accent hover transitions, monospace-free for button labels, `cn()` utility for conditional classes.

### 2026-03-27: Cross-team rename — Happy Path → ER Admission

- Updated `ScenarioToolbar.tsx`: button label `Happy Path` → `ER Admission`, endpoint `/api/scenario/happy-path` → `/api/scenario/er-admission`. Coordinated with Goose (backend), Jester (tests), Maverick (docs).

### 2026-03-09: Collapsible Agent Messages in AgentConversation

### 2026-03-27: Agent Directory Panel — Collapsible 3rd Column

- **New component**: `components/dashboard/AgentDirectory.tsx` — renders a collapsible panel in the Control Tower's 3rd grid column.
- **Two modes**: collapsed (40px vertical strip with Bot icon + "AGENTS" vertical text) and expanded (280px panel with agent cards).
- **Grid transition**: `transition-[grid-template-columns] duration-300 ease-in-out` on the main grid — columns smoothly resize between `[55fr_45fr_40px]` and `[50fr_40fr_280px]`.
- **Active agent detection**: derives from last message in SSE stream, highlights matching card with agent-color border/glow/bg.
- **Left accent bar pattern**: each card has a `w-1 rounded-full` bar using the agent's hex color, full opacity when active, 30% when inactive. Used a `getAccentHex()` helper to map Tailwind text-color classes to hex values for inline styles.
- **Custom header**: reproduced PaneHeader styling inline (accent gradient bar + icon + title) to add a collapse ChevronRight button without modifying the shared PaneHeader component interface.
- **Responsive**: hidden below `lg` breakpoint via `hidden lg:flex` wrapper div.
- **Zero new dependencies** — Bot, ChevronLeft, ChevronRight already in lucide-react.

### 2026-04-02: WI-P3-011 — Supply Chain TypeScript Types + Color Map + InventoryBoard

- **`types/api.ts` fully rewritten** — Replaced all bed management types (Bed, Patient, Transport, Reservation, BedState, PatientState, TransportPriority, AdmissionSource) with supply chain equivalents: Order, OrderItem, Product, Shipment, Allocation, Task. New enums: OrderState (9 values), ProductState (6), ShipmentState (7), TaskState (6), TaskType (5), FulfillmentPriority (3), SourceChannel (4). Config types renamed: HospitalConfig → FulfillmentConfig, CampusConfig → WarehouseConfig, UnitConfig → ZoneConfig. StateResponse keys updated to match.
- **`lib/colors.ts` fully rewritten** — Replaced patientStateBadge/bedStateBadge/bedStateDotColor/transportPriorityBadge with productStateBadge/productStateDotColor/orderStateBadge/shipmentStateBadge/fulfillmentPriorityBadge. Agent keyword colors updated from hospital agents to supply chain agents (supply-coord, demand, warehouse, logistics, compliance, etc). eventTypeColor keywords updated for supply chain domain.
- **`components/dashboard/BedBoard.tsx` → InventoryBoard** — Component fully replaced. Groups products by warehouse_id (not unit). Each cell shows SKU (mono), product name, state dot + label, qty on-hand / allocated, location code. Amber ring highlight when qty ≤ reorder_point. Uses Package icon instead of BedDouble. Grid min-width bumped to 130px for more data density.
- **Design decisions**: Kept same dark-mode Tailwind patterns, same props-down architecture (UI-001). No self-fetching. All types use string unions (not enums) per existing convention. AgentMessage and IntentTag kept as-is — domain-agnostic.

- **Collapsible long messages**: Messages >120 chars or containing `\n` start collapsed, showing only the first sentence as a summary with a `ChevronRight` toggle icon.
- **Animation technique**: Uses CSS `grid-template-rows: 0fr → 1fr` with `transition-[grid-template-rows]` for smooth expand/collapse — cleaner than max-height hacks, no JS measurement needed.
- **State management**: Parent `AgentConversation` holds a `Set<string>` of expanded message IDs. Toggle is passed down via `onToggle` callback. Short messages render with no toggle, unchanged.
- **Extracted `MessageBubble` sub-component**: Keeps the map body clean. Receives `msg`, `expanded`, `onToggle` props.
- **Summary extraction**: `summarize()` finds the first `.` or `\n` boundary; falls back to full content for short messages.
- **Zero new dependencies** — `ChevronRight` already in lucide-react, all styling via Tailwind utilities + tower-\* tokens.

### 2026-04-02: Cross-agent note from Scribe (Phase 3 kickoff)

- **Phase 3 supply chain pivot initiated.** Maverick designed full domain model — see decisions.md DOMAIN-P3-001, DOMAIN-P3-002, PLAN-P3-001.
- Viper assigned WI-P3-011 through WI-P3-014 (InventoryBoard, OrderQueue, ShipmentTracker, CommandCenter wiring). BedBoard→InventoryBoard, PatientQueue→OrderQueue, TransportQueue→ShipmentTracker.
- Goose is rewriting backend domain model (critical path). Jester prepping test fixtures. TypeScript types need to mirror new Pydantic models once Goose lands WI-P3-001.

### 2026-04-02: WI-P3-012 + WI-P3-013 — OrderQueue + ShipmentTracker

- **PatientQueue.tsx → OrderQueue** — Complete rewrite. Exports `OrderQueue` component. Props: `{ orders: Order[]; loading: boolean; error: string | null }`. Table columns: Customer, Order #, State, Priority, Channel, Destination, Items, ETA. Sort by priority rank (EXPEDITED=0, HIGH=1, STANDARD=2 via `priorityRank` map), then oldest `created_at`. State badge via `orderStateBadge()`, priority badge via `fulfillmentPriorityBadge()`. Items column shows count with singular/plural ("1 item" / "3 items"). ETA shows `{n}d` or "—" for null. Uses `ShoppingCart` icon.
- **TransportQueue.tsx → ShipmentTracker** — Complete rewrite. Exports `ShipmentTracker` component. Props: `{ shipments: Shipment[]; orders: Record<string, Order>; loading: boolean; error: string | null }`. Card-style list layout. Each card: carrier badge (teal accent), route with ArrowRight, customer name from orders lookup (fallback to order_id), tracking number in mono font, state badge via `shipmentStateBadge()` with human-readable labels (including "Delayed ⚠️"), scheduled date formatted as "Mon DD". Uses `Truck` icon.
- **Both components error-free** — no type errors in the rewritten files. Pre-existing errors in ControlTower.tsx and useApi.ts are expected (WI-P3-014 scope).
- **Design patterns preserved**: same dark-theme tower-\* tokens, error→loading→empty→data state flow, hover transitions, monospace for data fields, compact text-xs sizing, `cn()` for conditional classes.

### 2026-04-02: WI-P3-014 — CommandCenter Wiring (4 files)

- **`useApi.ts` rewritten** — Imports supply chain types (Product, Order, Task, Shipment, Allocation, FulfillmentConfig). State keys: products, orders, tasks, shipments, allocations, fulfillmentConfig. Maps `data.fulfillment_config` from API (snake_case) to `fulfillmentConfig` (camelCase).
- **`ControlTower.tsx` rewritten** — Icons: ShoppingCart, Package, Truck. Components imported by new names from old file paths (`OrderQueue` from PatientQueue.tsx, `InventoryBoard` from BedBoard.tsx, `ShipmentTracker` from TransportQueue.tsx). Left column: Order Queue → Inventory Board (flex-[2]) → Shipment Tracker. Middle + right columns unchanged (domain-agnostic). ShipmentTracker receives `orders` as Record (not array) for lookup.
- **`ScenarioToolbar.tsx`** — Replaced 5 hospital scenarios (ER/OR Admission, Disruption+Replan, EVS-Gated, Unit Transfer) with 3 supply chain scenarios: Standard Fulfillment, Rush Order, Supplier Delay.
- **`AgentDirectory.tsx`** — Replaced 6 hospital agents with 6 supply chain agents: supply-coordinator, demand-forecaster, inventory-allocator, warehouse-ops, logistics-planner, compliance-monitor. Names match agent keywords in `colors.ts`.
- **Key alignment**: StateResponse uses `fulfillment_config` (not `supply_chain_config`). InventoryBoard prop is `fulfillmentConfig` (not `supplyChainConfig`). Overrode task spec where type definitions differed. TypeScript compiles clean.

### 2026-04-02: WI-C-017 Early — Closet Domain Types + Colors

- **`types/api.ts` fully rewritten** — Removed all fulfillment center types (Order, OrderItem, Product, Task, Allocation, OrderState, ProductState, TaskType, FulfillmentPriority, SourceChannel, WarehouseConfig, ZoneConfig, FulfillmentConfig). Replaced with closet domain: SupplyCloset, SupplyItem, Vendor, CatalogEntry, PurchaseOrder, POLineItem, ScanResult, ReorderItem, Shipment (simplified). New enums: ItemCategory (8), ItemCriticality (3), ContractTier (3), POState (8), POApprovalStatus (4), ScanState (7), VendorStockStatus (4), ShipmentState (5). TaskState + IntentTag kept as-is. StateResponse keys: closets, supply_items, vendors, catalog, purchase_orders, scans, shipments.
- **`lib/colors.ts` fully rewritten** — Replaced productStateBadge/orderStateBadge/fulfillmentPriorityBadge with new helpers: `itemStatusColor(current, par, criticality)` + `itemStatusDot()` for supply item stock levels, `poStateBadge()`, `poApprovalBadge()`, `scanStateBadge()`, `contractTierBadge()`, `criticalityBadge()`, `vendorStockBadge()`, `shipmentStateBadge()`. Agent colors updated for new 5-agent roster: supply-coordinator, supply-scanner, catalog-sourcer, order-manager, compliance-gate. `eventTypeColor()` rewritten for 17 closet event types grouped by scan/sourcing/PO/shipment/restock/critical.
- **`hooks/useApi.ts` updated** — State shape: closets, supplyItems, vendors, catalog, purchaseOrders, scans, shipments. Maps snake_case API keys to camelCase.
- **Dashboard components updated** — PatientQueue.tsx (OrderQueue): now renders PurchaseOrders with PO#, vendor, state, approval, items, total. BedBoard.tsx (InventoryBoard): now renders SupplyItems grouped by closet, showing SKU, criticality badge, current/par quantities. TransportQueue.tsx (ShipmentTracker): simplified for new Shipment shape (po_id, closet_id, items_count, expected_delivery).
- **ControlTower.tsx updated** — Passes new data shape (supplyItems, purchaseOrders, closets) to child components. Section titles updated.
- **Build verified**: `tsc --noEmit` clean, `vite build` clean (1527 modules, 3.68s).

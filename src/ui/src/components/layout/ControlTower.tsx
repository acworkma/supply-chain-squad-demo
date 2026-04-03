import { ShoppingCart, Package, Truck, MessageSquare, Activity, Network } from "lucide-react";
import { PaneHeader } from "@/components/layout/PaneHeader";
import { ScenarioToolbar } from "@/components/layout/ScenarioToolbar";
import { OrderQueue } from "@/components/dashboard/OrderQueue";
import { InventoryBoard } from "@/components/dashboard/InventoryBoard";
import { ShipmentTracker } from "@/components/dashboard/ShipmentTracker";
import { AgentNetwork } from "@/components/dashboard/AgentNetwork";
import { AgentDirectory } from "@/components/dashboard/AgentDirectory";
import { AgentConversation } from "@/components/conversation/AgentConversation";
import { EventTimeline } from "@/components/timeline/EventTimeline";
import { ApprovalModal } from "@/components/approval/ApprovalModal";
import { useApi } from "@/hooks/useApi";
import { useSSE } from "@/hooks/useSSE";
import { cn } from "@/lib/utils";
import type { Event, AgentMessage, PurchaseOrder } from "@/types/api";
import { useCallback, useEffect, useRef, useState } from "react";

export function ControlTower() {
  const { supplyItems, purchaseOrders, shipments, closets, loading, error } = useApi();
  const { items: events, connected: eventsConnected, clear: clearEvents } = useSSE<Event>("/api/events/stream");
  const { items: messages, connected: messagesConnected, clear: clearMessages } = useSSE<AgentMessage>("/api/agent-messages/stream");

  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const toggleAgentPanel = useCallback(() => setAgentPanelOpen(prev => !prev), []);

  // ── Human-in-the-loop approval state ──
  const [pendingPO, setPendingPO] = useState<PurchaseOrder | null>(null);
  const lastHandledSeq = useRef(0);

  // Watch SSE events for POPendingHumanApproval
  useEffect(() => {
    for (const evt of events) {
      if (evt.sequence <= lastHandledSeq.current) continue;
      if (evt.event_type === "POPendingHumanApproval") {
        lastHandledSeq.current = evt.sequence;
        const poId = (evt.payload as Record<string, unknown>).po_id as string;
        // Fetch fresh PO data so modal has line items
        fetch("/api/state")
          .then((r) => r.json())
          .then((state) => {
            const po = state.purchase_orders?.[poId];
            if (po) setPendingPO(po);
          })
          .catch(() => {});
      }
    }
  }, [events]);

  const handleApprovalClose = useCallback(() => setPendingPO(null), []);

  const handleReset = useCallback(() => {
    clearEvents();
    clearMessages();
    lastHandledSeq.current = 0;
  }, [clearEvents, clearMessages]);

  const itemList = Object.values(supplyItems);
  const poList = Object.values(purchaseOrders);
  const shipmentList = Object.values(shipments);

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col">
      {/* ── Scenario Toolbar ── */}
      <ScenarioToolbar eventsConnected={eventsConnected} messagesConnected={messagesConnected} onReset={handleReset} />

      {/* ── Main Grid ── */}
      <div className={cn(
        "flex-1 overflow-hidden grid grid-rows-[1fr] gap-2 p-2 transition-[grid-template-columns] duration-300 ease-in-out",
        agentPanelOpen
          ? "grid-cols-[50fr_40fr_280px]"
          : "grid-cols-[55fr_45fr_40px]"
      )}>
      {/* ── Left Pane: Ops Dashboard ── */}
      <div className="flex flex-col gap-2 overflow-hidden">
        {/* Purchase Orders */}
        <section className="flex flex-col rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={ShoppingCart} title="Purchase Orders" badge={poList.length || undefined} />
          <div className="overflow-y-auto flex-1">
            <OrderQueue purchaseOrders={poList} loading={loading} error={error} />
          </div>
        </section>

        {/* Closet Inventory — takes the most space */}
        <section className="flex flex-col flex-[2] rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={Package} title="Closet Inventory" badge={itemList.length || undefined} />
          <div className="overflow-y-auto flex-1">
            <InventoryBoard supplyItems={itemList} loading={loading} error={error} />
          </div>
        </section>

        {/* Shipment Tracker — compact */}
        <section className="flex flex-col min-h-[100px] rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={Truck} title="Shipment Tracker" badge={shipmentList.length || undefined} />
          <div className="overflow-y-auto flex-1">
            <ShipmentTracker shipments={shipmentList} loading={loading} error={error} />
          </div>
        </section>
      </div>

      {/* ── Right Column: split top/bottom ── */}
      <div className="flex flex-col gap-2 overflow-hidden">
        {/* Agent Conversation — 55% of right column */}
        <section className="flex flex-col flex-[55] rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={MessageSquare} title="Agent Conversation" badge={messages.length || undefined} />
          <div className="overflow-y-auto flex-1 flex">
            <AgentConversation messages={messages} />
          </div>
        </section>

        {/* Event Timeline — 45% of right column */}
        <section className="flex flex-col flex-[45] rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={Activity} title="Event Timeline" badge={events.length || undefined} />
          <div className="overflow-y-auto flex-1 flex">
            <EventTimeline events={events} />
          </div>
        </section>
      </div>

      {/* ── Agent Directory (collapsible) ── */}
      <div className="hidden lg:flex overflow-hidden">
        <AgentDirectory isOpen={agentPanelOpen} onToggle={toggleAgentPanel} messages={messages} />
      </div>
      </div>

      {/* ── Agent Network Panel ── */}
      <section className="h-[200px] shrink-0 mx-2 mb-2 rounded-lg border border-tower-border bg-tower-surface overflow-hidden flex flex-col">
        <PaneHeader icon={Network} title="Agent Network" />
        <div className="flex-1 overflow-hidden">
          <AgentNetwork messages={messages} />
        </div>
      </section>

      {/* ── Human-in-the-loop Approval Modal ── */}
      {pendingPO && (
        <ApprovalModal po={pendingPO} onClose={handleApprovalClose} />
      )}
    </div>
  );
}

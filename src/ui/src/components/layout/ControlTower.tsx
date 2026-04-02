import { Users, BedDouble, Truck, MessageSquare, Activity, Network } from "lucide-react";
import { PaneHeader } from "@/components/layout/PaneHeader";
import { ScenarioToolbar } from "@/components/layout/ScenarioToolbar";
import { PatientQueue } from "@/components/dashboard/PatientQueue";
import { BedBoard } from "@/components/dashboard/BedBoard";
import { TransportQueue } from "@/components/dashboard/TransportQueue";
import { AgentNetwork } from "@/components/dashboard/AgentNetwork";
import { AgentDirectory } from "@/components/dashboard/AgentDirectory";
import { AgentConversation } from "@/components/conversation/AgentConversation";
import { EventTimeline } from "@/components/timeline/EventTimeline";
import { useApi } from "@/hooks/useApi";
import { useSSE } from "@/hooks/useSSE";
import { cn } from "@/lib/utils";
import type { Event, AgentMessage } from "@/types/api";
import { useCallback, useState } from "react";

export function ControlTower() {
  const { beds, patients, transports, hospitalConfig, loading, error } = useApi();
  const { items: events, connected: eventsConnected, clear: clearEvents } = useSSE<Event>("/api/events/stream");
  const { items: messages, connected: messagesConnected, clear: clearMessages } = useSSE<AgentMessage>("/api/agent-messages/stream");

  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const toggleAgentPanel = useCallback(() => setAgentPanelOpen(prev => !prev), []);

  const handleReset = useCallback(() => {
    clearEvents();
    clearMessages();
  }, [clearEvents, clearMessages]);

  const patientList = Object.values(patients);
  const bedList = Object.values(beds);
  const transportList = Object.values(transports);

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
        {/* Patient Queue */}
        <section className="flex flex-col rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={Users} title="Patient Queue" badge={patientList.length || undefined} />
          <div className="overflow-y-auto flex-1">
            <PatientQueue patients={patientList} loading={loading} error={error} />
          </div>
        </section>

        {/* Bed Board — takes the most space */}
        <section className="flex flex-col flex-[2] rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={BedDouble} title="Bed Board" badge={bedList.length || undefined} />
          <div className="overflow-y-auto flex-1">
            <BedBoard beds={bedList} patients={patients} hospitalConfig={hospitalConfig} loading={loading} error={error} />
          </div>
        </section>

        {/* Transport Queue — compact */}
        <section className="flex flex-col min-h-[100px] rounded-lg border border-tower-border bg-tower-surface overflow-hidden">
          <PaneHeader icon={Truck} title="Transport Queue" badge={transportList.length || undefined} />
          <div className="overflow-y-auto flex-1">
            <TransportQueue transports={transportList} patients={patients} loading={loading} error={error} />
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
    </div>
  );
}

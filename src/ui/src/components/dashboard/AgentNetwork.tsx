import { useEffect, useLayoutEffect, useRef, useState, useMemo, useCallback } from "react";
import { cn } from "@/lib/utils";
import { agentColor, intentTagBadge } from "@/lib/colors";
import type { AgentMessage, IntentTag } from "@/types/api";

/* ── Agent definitions ─────────────────────────────────────────── */

interface AgentDef {
  name: string;
  role: string;
}

const ORCHESTRATOR: AgentDef = { name: "supply-coordinator", role: "Supply Coordinator" };

const SPECIALISTS: AgentDef[] = [
  { name: "supply-scanner", role: "Supply Scanner Agent" },
  { name: "catalog-sourcer", role: "Catalog Sourcer Agent" },
  { name: "order-manager", role: "Order Manager Agent" },
  { name: "compliance-gate", role: "Compliance Gate Agent" },
];

/* ── Line descriptor ──────────────────────────────────────────── */

interface Line {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  agentName: string;
}

/* ── Props ─────────────────────────────────────────────────────── */

interface AgentNetworkProps {
  messages: AgentMessage[];
}

/* ── Component ─────────────────────────────────────────────────── */

export function AgentNetwork({ messages }: AgentNetworkProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const orchRef = useRef<HTMLDivElement>(null);
  const specRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [flashAgent, setFlashAgent] = useState<string | null>(null);
  const prevCountRef = useRef(0);

  /* ── Derive activity state from messages ── */

  const activeAgent = useMemo(() => {
    if (messages.length === 0) return null;
    return messages[messages.length - 1].agent_name;
  }, [messages]);

  const lastIntentByAgent = useMemo(() => {
    const map: Record<string, IntentTag> = {};
    for (const m of messages) {
      map[m.agent_name] = m.intent_tag;
    }
    return map;
  }, [messages]);

  /* ── Flash on new message ── */

  useEffect(() => {
    if (messages.length > prevCountRef.current && messages.length > 0) {
      const latest = messages[messages.length - 1].agent_name;
      setFlashAgent(latest);
      const timer = setTimeout(() => setFlashAgent(null), 400);
      return () => clearTimeout(timer);
    }
    prevCountRef.current = messages.length;
  }, [messages]);

  /* ── Compute SVG connector lines ── */

  const recomputeLines = useCallback(() => {
    const container = containerRef.current;
    const orch = orchRef.current;
    if (!container || !orch) return;

    const cRect = container.getBoundingClientRect();
    const oRect = orch.getBoundingClientRect();

    const newLines: Line[] = [];
    for (let i = 0; i < SPECIALISTS.length; i++) {
      const el = specRefs.current[i];
      if (!el) continue;
      const sRect = el.getBoundingClientRect();
      newLines.push({
        x1: oRect.left + oRect.width / 2 - cRect.left,
        y1: oRect.top + oRect.height - cRect.top,
        x2: sRect.left + sRect.width / 2 - cRect.left,
        y2: sRect.top - cRect.top,
        agentName: SPECIALISTS[i].name,
      });
    }
    setLines(newLines);
  }, []);

  useLayoutEffect(() => {
    recomputeLines();
  }, [recomputeLines]);

  useEffect(() => {
    const handleResize = () => recomputeLines();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [recomputeLines]);

  /* ── Render ── */

  return (
    <div ref={containerRef} className="relative flex flex-col items-center justify-center gap-5 h-full px-6 py-3">
      {/* SVG connector lines */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden>
        {lines.map((line) => {
          const isActive = activeAgent === line.agentName;
          const colors = agentColor(line.agentName);
          return (
            <line
              key={line.agentName}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke={isActive ? "currentColor" : "#374151"}
              strokeWidth={isActive ? 2 : 1}
              strokeDasharray={isActive ? "none" : "4 3"}
              className={cn("transition-all duration-300", isActive && colors.text)}
            />
          );
        })}
      </svg>

      {/* Orchestrator (top center) */}
      <AgentNode
        ref={orchRef}
        agent={ORCHESTRATOR}
        isActive={activeAgent === ORCHESTRATOR.name}
        isFlashing={flashAgent === ORCHESTRATOR.name}
        lastIntent={lastIntentByAgent[ORCHESTRATOR.name]}
      />

      {/* Specialists (bottom row) */}
      <div className="flex items-start justify-center gap-4 flex-wrap">
        {SPECIALISTS.map((spec, i) => (
          <AgentNode
            key={spec.name}
            ref={(el: HTMLDivElement | null) => { specRefs.current[i] = el; }}
            agent={spec}
            isActive={activeAgent === spec.name}
            isFlashing={flashAgent === spec.name}
            lastIntent={lastIntentByAgent[spec.name]}
          />
        ))}
      </div>
    </div>
  );
}

/* ── AgentNode ─────────────────────────────────────────────────── */

import { forwardRef } from "react";

interface AgentNodeProps {
  agent: AgentDef;
  isActive: boolean;
  isFlashing: boolean;
  lastIntent?: IntentTag;
}

const AgentNode = forwardRef<HTMLDivElement, AgentNodeProps>(
  function AgentNode({ agent, isActive, isFlashing, lastIntent }, ref) {
    const colors = agentColor(agent.name);

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs transition-all duration-300 min-w-[140px]",
          "bg-tower-surface",
          isActive
            ? `border-current ${colors.text} shadow-[0_0_12px_-3px_currentColor]`
            : "border-tower-border text-gray-500"
        )}
      >
        {/* Blinking indicator */}
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          {/* Flash ping (on new message) */}
          {isFlashing && (
            <span
              className={cn(
                "absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping",
                colors.bg
              )}
            />
          )}
          {/* Continuous pulse (while active) */}
          <span
            className={cn(
              "relative inline-flex h-2.5 w-2.5 rounded-full transition-colors duration-300",
              isActive ? cn(colors.bg.replace("/20", ""), "animate-pulse") : "bg-gray-600"
            )}
          />
        </span>

        {/* Name + intent */}
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className={cn("font-semibold truncate", isActive ? colors.text : "text-gray-300")}>
            {agent.role}
          </span>
          {lastIntent && (
            <span
              className={cn(
                "inline-flex items-center self-start rounded-sm px-1.5 py-0.5 text-[9px] font-bold uppercase leading-none",
                intentTagBadge(lastIntent)
              )}
            >
              {lastIntent}
            </span>
          )}
        </div>
      </div>
    );
  }
);

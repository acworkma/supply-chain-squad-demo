import { MessageSquare, Link, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { intentTagBadge, agentColor } from "@/lib/colors";
import type { AgentMessage } from "@/types/api";

interface AgentConversationProps {
  messages: AgentMessage[];
}

const LONG_CHAR_THRESHOLD = 120;

function relativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

/** True when content is long enough to warrant collapsing. */
function isLongMessage(content: string): boolean {
  return content.includes("\n") || content.length > LONG_CHAR_THRESHOLD;
}

/** First sentence (up to first `.` or `\n`), or the first 120 chars. */
function summarize(content: string): string {
  const dotIdx = content.indexOf(".");
  const nlIdx = content.indexOf("\n");
  let end = content.length;
  if (dotIdx > 0) end = dotIdx + 1;
  if (nlIdx > 0 && nlIdx < end) end = nlIdx;
  const summary = content.slice(0, end).trim();
  return summary.length < content.trim().length ? summary : content;
}

// ── MessageBubble ──────────────────────────────────────────────

interface MessageBubbleProps {
  msg: AgentMessage;
  expanded: boolean;
  onToggle: () => void;
}

function MessageBubble({ msg, expanded, onToggle }: MessageBubbleProps) {
  const colors = agentColor(msg.agent_name);
  const long = isLongMessage(msg.content);

  return (
    <div className="flex gap-2.5 group">
      {/* Avatar */}
      <div
        className={cn(
          "h-7 w-7 rounded-full ring-1 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5",
          colors.ring,
          colors.bg,
          colors.text
        )}
      >
        {msg.agent_name.charAt(0).toUpperCase()}
      </div>

      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn("text-xs font-semibold", colors.text)}>
            {msg.agent_name}
          </span>
          <span className="text-[10px] text-gray-600">{msg.agent_role}</span>
          <span
            className={cn(
              "inline-flex items-center rounded-sm px-1.5 py-0.5 text-[9px] font-bold uppercase",
              intentTagBadge(msg.intent_tag)
            )}
          >
            {msg.intent_tag}
          </span>
          <span className="text-[10px] text-gray-600 font-mono ml-auto shrink-0">
            {relativeTime(msg.timestamp)}
          </span>
        </div>

        {/* Content — collapsible for long messages */}
        {long ? (
          <>
            <button
              type="button"
              onClick={onToggle}
              className="flex items-start gap-1 mt-1 text-left w-full group/toggle"
            >
              <ChevronRight
                className={cn(
                  "h-3.5 w-3.5 shrink-0 mt-0.5 text-gray-500 transition-transform duration-200",
                  expanded && "rotate-90"
                )}
              />
              <span className="text-xs text-gray-300 leading-relaxed">
                {expanded ? "" : summarize(msg.content)}
              </span>
            </button>
            <div
              className={cn(
                "grid transition-[grid-template-rows] duration-200 ease-in-out",
                expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
              )}
            >
              <div className="overflow-hidden min-h-0">
                <p className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap pl-[18px]">
                  {msg.content}
                </p>
              </div>
            </div>
          </>
        ) : (
          <p className="text-xs text-gray-300 mt-1 leading-relaxed whitespace-pre-wrap">
            {msg.content}
          </p>
        )}

        {/* Related events */}
        {msg.related_event_ids.length > 0 && (
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            <Link className="h-3 w-3 text-gray-600" />
            {msg.related_event_ids.map((eid) => (
              <span
                key={eid}
                className="inline-flex items-center rounded-sm bg-tower-border px-1.5 py-0.5 text-[9px] font-mono text-gray-400 hover:text-gray-200 transition-colors cursor-default"
                title={`Event: ${eid}`}
              >
                {eid.slice(0, 8)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── AgentConversation ──────────────────────────────────────────

export function AgentConversation({ messages }: AgentConversationProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggle = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-4 mb-4">
          <MessageSquare className="h-6 w-6 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">Waiting for scenario to start…</p>
        <p className="text-xs text-gray-600 mt-1.5 max-w-[240px]">
          Agent messages and tool calls will stream here in real time
        </p>
        <div className="mt-6 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-tower-accent/40 animate-pulse" />
          <span className="h-1.5 w-1.5 rounded-full bg-tower-accent/40 animate-pulse [animation-delay:300ms]" />
          <span className="h-1.5 w-1.5 rounded-full bg-tower-accent/40 animate-pulse [animation-delay:600ms]" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col w-full p-3 space-y-3">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          msg={msg}
          expanded={expandedIds.has(msg.id)}
          onToggle={() => toggle(msg.id)}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

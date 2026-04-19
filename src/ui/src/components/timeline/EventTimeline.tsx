import { Activity, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { eventTypeColor } from "@/lib/colors";
import type { Event } from "@/types/api";

interface EventTimelineProps {
  events: Event[];
}

function relativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

function EventRow({ event }: { event: Event }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-tower-border/40">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-1.5 text-left hover:bg-white/2 transition-colors group text-xs"
      >
        <ChevronRight
          className={cn(
            "h-3 w-3 text-gray-600 transition-transform shrink-0",
            expanded && "rotate-90"
          )}
        />
        <span className="text-gray-500 font-mono w-8 shrink-0 text-right">
          #{event.sequence}
        </span>
        <span className="text-gray-500 font-mono w-14 shrink-0">
          {relativeTime(event.timestamp)}
        </span>
        <span
          className={cn(
            "inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] font-semibold shrink-0",
            eventTypeColor(event.event_type)
          )}
        >
          {event.event_type}
        </span>
        <span className="text-gray-500 font-mono text-[10px] truncate ml-auto">
          {event.entity_id}
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-2 pl-18 space-y-2">
          {/* State diff */}
          {event.state_diff && (
            <div className="flex items-center gap-2 text-[11px]">
              <span className="text-gray-500">State:</span>
              <span className="font-mono text-orange-400">{event.state_diff.from_state}</span>
              <span className="text-gray-600">→</span>
              <span className="font-mono text-emerald-400">{event.state_diff.to_state}</span>
            </div>
          )}

          {/* Payload */}
          {Object.keys(event.payload).length > 0 && (
            <pre className="text-[10px] text-gray-400 bg-tower-bg rounded-sm p-2 overflow-x-auto font-mono leading-relaxed">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function EventTimeline({ events }: EventTimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-4 mb-4">
          <Activity className="h-6 w-6 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">No events yet</p>
        <p className="text-xs text-gray-600 mt-1.5 max-w-[240px]">
          System events will appear chronologically as scenarios execute
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col w-full">
      {events.map((event) => (
        <EventRow key={event.id} event={event} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

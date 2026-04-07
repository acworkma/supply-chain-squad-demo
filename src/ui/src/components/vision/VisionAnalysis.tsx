import { useCallback, useEffect, useRef, useState } from "react";
import { ScanLine, Play, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScanImageResponse } from "@/components/vision/ImageUpload";

interface VisionAnalysisProps {
  scanResult: ScanImageResponse;
  imageFile: File;
  onStartWorkflow: () => void;
}

function statusDot(current: number, par: number): string {
  if (current === 0) return "bg-gray-500";
  const ratio = par > 0 ? current / par : 1;
  if (ratio < 0.3) return "bg-red-500";
  if (ratio < 1) return "bg-amber-500";
  return "bg-emerald-500";
}

function statusText(current: number, par: number): string {
  if (current === 0) return "text-gray-400";
  const ratio = par > 0 ? current / par : 1;
  if (ratio < 0.3) return "text-red-400";
  if (ratio < 1) return "text-amber-400";
  return "text-emerald-400";
}

export function VisionAnalysis({ scanResult, imageFile, onStartWorkflow }: VisionAnalysisProps) {
  const [phase, setPhase] = useState<"scanning" | "revealing" | "done">("scanning");
  const [revealedCount, setRevealedCount] = useState(0);
  const [starting, setStarting] = useState(false);
  const imageUrl = useRef<string>("");
  const scanLinePos = useRef(0);
  const animFrameRef = useRef<number>(0);

  // Create stable object URL
  useEffect(() => {
    imageUrl.current = URL.createObjectURL(imageFile);
    return () => URL.revokeObjectURL(imageUrl.current);
  }, [imageFile]);

  // Phase 1: scanning animation for 2 seconds, then reveal items
  useEffect(() => {
    const timer = setTimeout(() => setPhase("revealing"), 2000);
    return () => clearTimeout(timer);
  }, []);

  // Animate scan line during scanning phase
  useEffect(() => {
    if (phase !== "scanning") {
      cancelAnimationFrame(animFrameRef.current);
      return;
    }
    let start: number | null = null;
    function tick(ts: number) {
      if (!start) start = ts;
      const elapsed = ts - start;
      // One full sweep every 1.2s
      scanLinePos.current = (elapsed % 1200) / 1200;
      const el = document.getElementById("vision-scan-line");
      if (el) el.style.top = `${scanLinePos.current * 100}%`;
      animFrameRef.current = requestAnimationFrame(tick);
    }
    animFrameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [phase]);

  // Phase 2: progressively reveal items
  useEffect(() => {
    if (phase !== "revealing") return;
    if (revealedCount >= scanResult.items.length) {
      setPhase("done");
      return;
    }
    const timer = setTimeout(() => setRevealedCount((c) => c + 1), 200);
    return () => clearTimeout(timer);
  }, [phase, revealedCount, scanResult.items.length]);

  const handleStart = useCallback(async () => {
    setStarting(true);
    onStartWorkflow();
  }, [onStartWorkflow]);

  return (
    <div className="flex items-center justify-center h-full w-full p-6">
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ── Left: Uploaded image with scan overlay ── */}
        <div className="relative rounded-xl border border-tower-border bg-tower-surface overflow-hidden aspect-[4/3]">
          <img
            src={imageUrl.current}
            alt="Supply closet"
            className="w-full h-full object-cover"
          />
          {/* Scanning overlay */}
          {phase === "scanning" && (
            <div className="absolute inset-0 bg-tower-accent/5">
              <div
                id="vision-scan-line"
                className="absolute left-0 right-0 h-0.5 bg-tower-accent shadow-[0_0_12px_2px] shadow-tower-accent/60"
                style={{ top: "0%" }}
              />
              {/* Corner brackets */}
              <div className="absolute top-3 left-3 w-6 h-6 border-t-2 border-l-2 border-tower-accent/70 rounded-tl" />
              <div className="absolute top-3 right-3 w-6 h-6 border-t-2 border-r-2 border-tower-accent/70 rounded-tr" />
              <div className="absolute bottom-3 left-3 w-6 h-6 border-b-2 border-l-2 border-tower-accent/70 rounded-bl" />
              <div className="absolute bottom-3 right-3 w-6 h-6 border-b-2 border-r-2 border-tower-accent/70 rounded-br" />
            </div>
          )}
          {/* Check overlay when done */}
          {phase === "done" && (
            <div className="absolute inset-0 bg-black/20 flex items-center justify-center">
              <div className="rounded-full bg-emerald-500/20 p-3 backdrop-blur-sm border border-emerald-500/30">
                <CheckCircle2 className="h-8 w-8 text-emerald-400" />
              </div>
            </div>
          )}
          {/* Closet label */}
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent px-4 py-3">
            <p className="text-sm font-semibold text-gray-100">{scanResult.closet_name}</p>
            <p className="text-xs text-gray-400 font-mono">{scanResult.closet_id}</p>
          </div>
        </div>

        {/* ── Right: Analysis results ── */}
        <div className="flex flex-col rounded-xl border border-tower-border bg-tower-surface overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-tower-border flex items-center gap-2">
            <ScanLine className="h-4 w-4 text-tower-accent" />
            <h3 className="text-sm font-semibold text-gray-200">
              {phase === "scanning"
                ? "Analyzing image…"
                : phase === "revealing"
                  ? `Detecting items… (${revealedCount}/${scanResult.items.length})`
                  : `${scanResult.items.length} items detected`}
            </h3>
            {phase === "scanning" && (
              <div className="ml-auto flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-tower-accent animate-pulse" />
                <span className="h-1.5 w-1.5 rounded-full bg-tower-accent animate-pulse [animation-delay:200ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-tower-accent animate-pulse [animation-delay:400ms]" />
              </div>
            )}
          </div>

          {/* Items list */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {phase === "scanning" ? (
              // Placeholder shimmer rows
              <div className="space-y-2 py-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-10 rounded bg-white/[0.03] animate-pulse"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
            ) : (
              scanResult.items.map((item, index) => {
                const visible = index < revealedCount;
                return (
                  <div
                    key={item.sku}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent transition-all duration-300",
                      visible
                        ? "opacity-100 translate-x-0 bg-white/[0.03] border-tower-border/50"
                        : "opacity-0 translate-x-4",
                    )}
                  >
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full shrink-0",
                        visible ? statusDot(item.current_quantity, item.par_level) : "bg-gray-700",
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-200 truncate">
                        {item.name}
                      </p>
                      <p className="text-[10px] text-gray-500 font-mono">{item.sku}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <span
                        className={cn(
                          "text-sm font-semibold font-mono",
                          visible ? statusText(item.current_quantity, item.par_level) : "text-gray-600",
                        )}
                      >
                        {item.current_quantity}
                      </span>
                      <span className="text-[10px] text-gray-600 font-mono"> / {item.par_level}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Start workflow button */}
          <div className="px-4 py-3 border-t border-tower-border">
            <button
              onClick={handleStart}
              disabled={phase !== "done" || starting}
              className={cn(
                "w-full inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-200",
                phase === "done" && !starting
                  ? "bg-tower-accent text-gray-950 hover:bg-tower-accent/90 shadow-lg shadow-tower-accent/20"
                  : "bg-tower-border text-gray-500 cursor-not-allowed",
              )}
            >
              {starting ? (
                <>
                  <span className="h-4 w-4 border-2 border-gray-950 border-t-transparent rounded-full animate-spin" />
                  Starting…
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Start Restock Workflow
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

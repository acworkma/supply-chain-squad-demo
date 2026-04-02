import { Package } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * CommandCenter — main app shell for the Supply Chain demo.
 *
 * Same dark-theme three-column grid layout as the supply closet replenishment
 * "ControlTower", adapted for supply chain domain. Pane content
 * will be built in Phase 3 (in the new Codespace).
 */
export function CommandCenter() {
  return (
    <div className="h-screen flex flex-col bg-tower-bg text-gray-100 overflow-hidden">
      {/* Top bar placeholder — ScenarioToolbar will go here */}
      <header className="flex items-center gap-3 px-4 py-3 border-b border-tower-border bg-tower-surface">
        <Package className="h-5 w-5 text-tower-accent" />
        <h1 className="text-base font-semibold tracking-wide">
          Supply Chain Command Center
        </h1>
        <span className="ml-auto text-xs text-gray-500">scaffold — domain panes coming soon</span>
      </header>

      {/* Grid placeholder — panes will be wired in Phase 3 */}
      <main className="flex-1 grid grid-cols-[50fr_40fr_280px] gap-px bg-tower-border overflow-hidden">
        {/* Left column — operations dashboard */}
        <div className="bg-tower-surface flex items-center justify-center text-gray-500 text-sm">
          Operations Dashboard (Orders, Inventory, Shipments)
        </div>

        {/* Middle column — agent conversation + event timeline */}
        <div className="bg-tower-surface flex items-center justify-center text-gray-500 text-sm">
          Agent Conversation &amp; Event Timeline
        </div>

        {/* Right sidebar — agent directory */}
        <div className="bg-tower-surface flex items-center justify-center text-gray-500 text-sm">
          Agent Directory
        </div>
      </main>
    </div>
  );
}

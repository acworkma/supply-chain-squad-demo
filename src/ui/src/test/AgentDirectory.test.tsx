import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentDirectory } from "@/components/dashboard/AgentDirectory";
import type { AgentMessage, IntentTag } from "@/types/api";

/* ── Mock data ───────────────────────────────────────────────── */

const mockMessages: AgentMessage[] = [
  {
    id: "msg-1",
    agent_name: "bed-coordinator",
    agent_role: "Supervisor",
    intent_tag: "PROPOSE" as IntentTag,
    content: "Test message",
    timestamp: new Date().toISOString(),
    related_event_ids: [],
  },
  {
    id: "msg-2",
    agent_name: "transport-ops",
    agent_role: "Worker",
    intent_tag: "EXECUTE" as IntentTag,
    content: "Transport scheduled",
    timestamp: new Date().toISOString(),
    related_event_ids: [],
  },
];

const AGENT_DISPLAY_NAMES = [
  "Bed Coordinator Assistant",
  "Predictive Capacity",
  "Bed Allocation",
  "EVS Tasking",
  "Transport Ops",
  "Policy & Safety",
];

/* ── Tests ───────────────────────────────────────────────────── */

describe("AgentDirectory", () => {
  // 1. Collapsed state renders vertical AGENTS label
  it("renders vertical AGENTS label when collapsed", () => {
    render(
      <AgentDirectory isOpen={false} onToggle={() => {}} messages={[]} />
    );
    expect(screen.getByText("AGENTS")).toBeInTheDocument();
  });

  // 2. Collapsed state calls onToggle on click
  it("calls onToggle when the collapsed strip is clicked", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <AgentDirectory isOpen={false} onToggle={onToggle} messages={[]} />
    );

    const strip = screen.getByText("AGENTS").closest("button")!;
    await user.click(strip);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  // 3. Expanded state shows all 6 agent names
  it("shows all 6 agent role names when expanded", () => {
    render(
      <AgentDirectory isOpen={true} onToggle={() => {}} messages={[]} />
    );

    for (const name of AGENT_DISPLAY_NAMES) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
  });

  // 4. Expanded state shows Agent Directory header
  it('shows "Agent Directory" heading when expanded', () => {
    render(
      <AgentDirectory isOpen={true} onToggle={() => {}} messages={[]} />
    );
    expect(screen.getByText("Agent Directory")).toBeInTheDocument();
  });

  // 5. Active agent gets highlighted
  it("highlights the card for the active agent (last message sender)", () => {
    const { container } = render(
      <AgentDirectory
        isOpen={true}
        onToggle={() => {}}
        messages={mockMessages}
      />
    );

    // The last message is from "transport-ops" → Transport Ops card
    const transportLabel = screen.getByText("Transport Ops");
    const card = transportLabel.closest("[data-active]") ??
      transportLabel.closest("div");

    // The active card should have a distinguishing attribute or brighter style
    expect(
      card?.getAttribute("data-active") === "true" ||
        card?.className.match(/ring|border-.*-400|bg-.*-900|highlight|active/)
    ).toBeTruthy();
  });

  // 6. Collapse button calls onToggle
  it("calls onToggle when the collapse button is clicked in expanded view", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <AgentDirectory isOpen={true} onToggle={onToggle} messages={[]} />
    );

    // The expanded panel has a dedicated collapse/chevron button separate from agent cards
    const buttons = screen.getAllByRole("button");
    // Find the collapse button — it's typically in the header area, not an agent card
    const collapseBtn = buttons.find(
      (btn) =>
        btn.querySelector("svg") !== null ||
        btn.textContent?.includes("«") ||
        btn.textContent?.includes("‹") ||
        btn.getAttribute("aria-label")?.match(/collapse|close|toggle/i)
    );
    expect(collapseBtn).toBeDefined();

    await user.click(collapseBtn!);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});

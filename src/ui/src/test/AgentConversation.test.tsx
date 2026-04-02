import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentConversation } from "@/components/conversation/AgentConversation";
import type { AgentMessage, IntentTag } from "@/types/api";

/* ── jsdom stubs ─────────────────────────────────────────────── */

beforeAll(() => {
  // jsdom doesn't implement scrollIntoView
  Element.prototype.scrollIntoView = () => {};
});

/* ── Factory helper ─────────────────────────────────────────── */

let _seq = 0;
function makeMessage(overrides: Partial<AgentMessage> = {}): AgentMessage {
  _seq += 1;
  return {
    id: `msg-${_seq}`,
    agent_name: "Supply Coordinator",
    agent_role: "Supervisor",
    content: "Short status update.",
    intent_tag: "EXECUTE" as IntentTag,
    timestamp: new Date().toISOString(),
    related_event_ids: [],
    ...overrides,
  };
}

/* ── Test data ───────────────────────────────────────────────── */

const SHORT_CONTENT = "Scan SCAN-001 initiated for closet CLO-ICU-01."; // 47 chars, no newline
const LONG_CONTENT =
  "Scan SCAN-001 has identified 3 items below par level in ICU Main Closet (CLO-ICU-01). " +
  "Critical items include IV Saline (2 units remaining, par level 20) and Nitrile Gloves " +
  "(5 boxes remaining, par level 30). Initiating vendor sourcing for immediate replenishment.";
const LONG_SUMMARY =
  "Scan SCAN-001 has identified 3 items below par level in ICU Main Closet (CLO-ICU-01).";
const MULTILINE_CONTENT =
  "IV Saline restocked to par level after shipment SHP-001 delivered to ICU Main Closet.\nVendor sourcing confirmed for Nitrile Gloves.\nETA is 12 minutes.";
const MULTILINE_SUMMARY = "IV Saline restocked to par level after shipment SHP-001 delivered to ICU Main Closet.";

/** Find the chevron SVG inside a toggle button and check its rotation class. */
function chevronHasRotate(button: HTMLElement): boolean {
  const svg = button.querySelector("svg");
  return svg?.classList.contains("rotate-90") ?? false;
}

/* ── Tests ───────────────────────────────────────────────────── */

describe("AgentConversation", () => {
  // ---- 7. Empty state ----
  it("shows waiting state when there are no messages", () => {
    render(<AgentConversation messages={[]} />);
    expect(screen.getByText(/waiting for scenario/i)).toBeInTheDocument();
  });

  // ---- 1. Short message renders fully visible ----
  it("renders a short message fully visible with no toggle", () => {
    const msg = makeMessage({ content: SHORT_CONTENT });
    render(<AgentConversation messages={[msg]} />);

    // Full content rendered in a plain <p>, not inside a button
    expect(screen.getByText(SHORT_CONTENT)).toBeInTheDocument();

    // No toggle button for a short message
    const buttons = screen.queryAllByRole("button");
    expect(buttons).toHaveLength(0);
  });

  // ---- 2. Long message shows summary when collapsed ----
  it("shows only the first sentence as summary for a long message", () => {
    const msg = makeMessage({ content: LONG_CONTENT });
    render(<AgentConversation messages={[msg]} />);

    // Summary appears inside the toggle button
    expect(screen.getByText(LONG_SUMMARY)).toBeInTheDocument();

    // Toggle button present with un-rotated chevron (collapsed)
    const btn = screen.getByRole("button");
    expect(chevronHasRotate(btn)).toBe(false);
  });

  // ---- 3. Long message with newline shows first line as summary ----
  it("shows first line as summary when content contains newlines", () => {
    const msg = makeMessage({ content: MULTILINE_CONTENT });
    render(<AgentConversation messages={[msg]} />);

    // First line (up to period before newline) shown as summary
    expect(screen.getByText(MULTILINE_SUMMARY)).toBeInTheDocument();

    // Chevron not rotated
    const btn = screen.getByRole("button");
    expect(chevronHasRotate(btn)).toBe(false);
  });

  // ---- 4. Clicking chevron expands message ----
  it("expands full content when the toggle is clicked", async () => {
    const user = userEvent.setup();
    const msg = makeMessage({ content: LONG_CONTENT });
    render(<AgentConversation messages={[msg]} />);

    const btn = screen.getByRole("button");
    await user.click(btn);

    // Chevron rotates to indicate expanded state
    expect(chevronHasRotate(btn)).toBe(true);

    // Summary text inside button is cleared when expanded
    const summarySpan = btn.querySelector("span");
    expect(summarySpan?.textContent).toBe("");

    // Full content visible in the expanded grid area
    expect(screen.getByText(LONG_CONTENT)).toBeInTheDocument();
  });

  // ---- 5. Clicking expanded message collapses it ----
  it("collapses back to summary on second toggle click", async () => {
    const user = userEvent.setup();
    const msg = makeMessage({ content: LONG_CONTENT });
    render(<AgentConversation messages={[msg]} />);

    const btn = screen.getByRole("button");

    // Expand
    await user.click(btn);
    expect(chevronHasRotate(btn)).toBe(true);

    // Collapse
    await user.click(btn);
    expect(chevronHasRotate(btn)).toBe(false);

    // Summary text reappears in the button
    expect(screen.getByText(LONG_SUMMARY)).toBeInTheDocument();
  });

  // ---- 6. Multiple messages track expand state independently ----
  it("tracks expand/collapse state independently per message", async () => {
    const user = userEvent.setup();
    const secondContent =
      "Second long message that also exceeds the one-hundred-and-twenty character threshold and should be collapsed initially. " +
      "It contains additional detail about inventory replenishment beyond the summary.";
    const msg1 = makeMessage({ id: "m1", content: LONG_CONTENT });
    const msg2 = makeMessage({ id: "m2", content: secondContent });

    render(<AgentConversation messages={[msg1, msg2]} />);

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);

    // Both collapsed initially
    expect(chevronHasRotate(buttons[0])).toBe(false);
    expect(chevronHasRotate(buttons[1])).toBe(false);

    // Expand only the first
    await user.click(buttons[0]);

    expect(chevronHasRotate(buttons[0])).toBe(true);
    expect(chevronHasRotate(buttons[1])).toBe(false);
  });

  // ---- 8. Related event IDs render when present ----
  it("renders related event ID chips when present", () => {
    const eventIds = ["evt-abc12345-def", "evt-99887766-xyz"];
    const msg = makeMessage({
      content: SHORT_CONTENT,
      related_event_ids: eventIds,
    });
    render(<AgentConversation messages={[msg]} />);

    for (const eid of eventIds) {
      expect(screen.getByText(eid.slice(0, 8))).toBeInTheDocument();
    }
  });

  it("does not render event chips when related_event_ids is empty", () => {
    const msg = makeMessage({ content: SHORT_CONTENT, related_event_ids: [] });
    render(<AgentConversation messages={[msg]} />);

    const chips = document.querySelectorAll("[title^='Event:']");
    expect(chips).toHaveLength(0);
  });
});

import '@testing-library/jest-dom/vitest'

// jsdom does not provide EventSource — stub it for tests
class EventSourceStub {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = EventSourceStub.CLOSED;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  close() {
    this.readyState = EventSourceStub.CLOSED;
  }
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {
    return false;
  }
}

if (typeof globalThis.EventSource === 'undefined') {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).EventSource = EventSourceStub;
}

import { useEffect, useRef, useState } from "react";

/**
 * useApi — generic polling hook for the /api/state endpoint.
 *
 * This is a stub for the supply chain domain. The state shape will be
 * defined in Phase 3 when domain models are implemented.
 */

interface ApiState {
  loading: boolean;
  error: string | null;
}

const POLL_INTERVAL = 2000;

export function useApi(): ApiState {
  const [state, setState] = useState<ApiState>({
    loading: true,
    error: null,
  });

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    async function fetchState() {
      try {
        const res = await fetch("/api/health");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (mountedRef.current) {
          setState({ loading: false, error: null });
        }
      } catch (err) {
        if (mountedRef.current) {
          setState({
            loading: false,
            error: err instanceof Error ? err.message : "Unknown error",
          });
        }
      }
    }

    fetchState();
    const id = setInterval(fetchState, POLL_INTERVAL);

    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, []);

  return state;
}

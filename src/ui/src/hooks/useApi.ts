import { useEffect, useRef, useState } from "react";
import type { Bed, Patient, Task, Transport, Reservation, HospitalConfig, StateResponse } from "@/types/api";

interface ApiState {
  beds: Record<string, Bed>;
  patients: Record<string, Patient>;
  tasks: Record<string, Task>;
  transports: Record<string, Transport>;
  reservations: Record<string, Reservation>;
  hospitalConfig: HospitalConfig | null;
  loading: boolean;
  error: string | null;
}

const POLL_INTERVAL = 2000;

export function useApi(): ApiState {
  const [state, setState] = useState<ApiState>({
    beds: {},
    patients: {},
    tasks: {},
    transports: {},
    reservations: {},
    hospitalConfig: null,
    loading: true,
    error: null,
  });

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    async function fetchState() {
      try {
        const res = await fetch("/api/state");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: StateResponse = await res.json();
        if (mountedRef.current) {
          setState({
            beds: data.beds ?? {},
            patients: data.patients ?? {},
            tasks: data.tasks ?? {},
            transports: data.transports ?? {},
            reservations: data.reservations ?? {},
            hospitalConfig: data.hospital_config ?? null,
            loading: false,
            error: null,
          });
        }
      } catch (err) {
        if (mountedRef.current) {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: err instanceof Error ? err.message : "Unknown error",
          }));
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

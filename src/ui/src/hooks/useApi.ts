import { useEffect, useRef, useState } from "react";
import type { SupplyCloset, SupplyItem, Vendor, CatalogEntry, PurchaseOrder, ScanResult, Shipment, StateResponse } from "@/types/api";

interface ApiState {
  closets: Record<string, SupplyCloset>;
  supplyItems: Record<string, SupplyItem>;
  vendors: Record<string, Vendor>;
  catalog: Record<string, CatalogEntry>;
  purchaseOrders: Record<string, PurchaseOrder>;
  scans: Record<string, ScanResult>;
  shipments: Record<string, Shipment>;
  loading: boolean;
  error: string | null;
}

const POLL_INTERVAL = 2000;

export function useApi(): ApiState {
  const [state, setState] = useState<ApiState>({
    closets: {},
    supplyItems: {},
    vendors: {},
    catalog: {},
    purchaseOrders: {},
    scans: {},
    shipments: {},
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
            closets: data.closets ?? {},
            supplyItems: data.supply_items ?? {},
            vendors: data.vendors ?? {},
            catalog: data.catalog ?? {},
            purchaseOrders: data.purchase_orders ?? {},
            scans: data.scans ?? {},
            shipments: data.shipments ?? {},
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

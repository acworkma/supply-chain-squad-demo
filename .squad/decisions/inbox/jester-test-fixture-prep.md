### 2026-04-02: Test infrastructure prepped for supply chain domain model
**By:** Jester (Tester)
**What:** Updated `conftest.py`, `test_models.py`, and `test_transitions.py` to use supply chain entities (Order, Product, Shipment, Allocation) and enums (OrderState, ProductState, ShipmentState, FulfillmentPriority, SourceChannel). Tests import from `app.models.entities` and `app.models.transitions` using the new names from the design spec. They will fail on import until Goose lands WI-P3-001 + WI-P3-002. Estimated ~245 tests across both files once runnable.
**Why:** Parallel prep (WI-P3-010 PREP) — tests are ready to validate domain code as soon as it lands, unblocking immediate verification.

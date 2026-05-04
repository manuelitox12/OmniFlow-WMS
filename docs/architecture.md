# OmniFlow-WMS Architecture Documentation

## 1. System Overview
OmniFlow-WMS is designed to operate in high-volume warehouse environments, providing real-time tracking of order fulfillment processes. The architecture is optimized for minimal latency, preventing bottlenecks during peak physical operations.

## 2. Core Business Flow (State Machine)
The core of the application revolves around a strict state machine tracking physical inventory movement. Orders flow through the following states:

1. **Pendiente (Pending):** Order is ingested into the system. It is visible on the dashboard but physical preparation has not started.
2. **Empacando (Packing):** An operator claims the order. The system begins tracking active labor time.
3. **Empacado (Packed):** The physical preparation is complete. The operator inputs the final "Bultos" (Package Count) and the total labor time is frozen and logged.
4. **Retirado (Shipped/Removed):** The packages leave the facility. The system logs the specific transport entity and timestamps the exit.

*Note: There is an alternative "Directo" (Direct-Ship) flow that bypasses the packing state for immediate dispatch.*

## 3. Multi-Tenant Strategy
To ensure enterprise-grade data isolation (SaaS compatibility), the system abandons shared-table row-level security in favor of a **Database-per-Tenant** model.
- Each client/tenant connects to a physically isolated SQLite database (designed for seamless vertical migration to PostgreSQL schemas).
- Branding, shift schedules, and dynamic break times (e.g., lunch hour deductions) are strictly localized per tenant.

## 4. Security & Auditing Implementations
- **Zero-Trust Input:** All dynamic SQL queries utilize strict parameterized dictionary mapping to neutralize SQL injection vectors.
- **Active CSRF Blocking:** Nonces and tokens are supplemented by an active middleware interceptor validating `Origin` and `Referer` headers against the host server.
- **Traceability:** The `services/auditoria.py` module acts as a shadow-logger, recording immutable before/after state changes (deltas) across critical database tables to prevent un-auditable tampering.

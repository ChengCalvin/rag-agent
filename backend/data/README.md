# NovaMart synthetic data

Everything here is invented for a prototype. There are no real people, customers, emails, addresses or policies. Email addresses use `example.com` and `example.test`; addresses use the fictitious postcode prefix `ZZ`. Persona selection (`NOVAMART_USER`) simulates sign-in and is not authentication.

## Layout

- `docs/*.md`: 8 policy documents and 3 product documents, each with YAML front-matter. Only this folder is indexed; this README is not.
- `orders.json`: 10 orders across 3 stores.
- `users.json`: 4 personas.

## Document front-matter

| Field | Meaning |
|---|---|
| `id` | Unique document id (cited in Sources) |
| `title` | Document title |
| `doc_type` | `policy` or `product` |
| `audience` | `all_staff`, or `manager` (managers and regional managers only) |

Extra fields are free-form parameters. `returns-policy` carries `return_window_days` (30), `excluded_categories`, `category_exceptions` (electronics, 14 days) and `non_returnable_conditions`. `store-operations` carries `escalation_contact`; it is audience `all_staff` and indexed like every other document.

Restricted documents: `manager-approvals` (policy) and `product-novabook-launch-briefing` (product) have `audience: manager`. Each product document holds exactly one fenced ASCII diagram.

## Deliberate gaps

The documents are silent on these topics, so questions about them must be refused with the escalation contact:

- Bulk or corporate orders
- International shipping and customs
- Trade-in and buy-back of used devices
- Employee scheduling, pay and leave
- Installation and assembly services

## Orders

Order id format: `NM-` followed by 6 digits. Store ids are `store-7`, `store-12`, `store-19`; stores 7 and 12 are in region `north`, store 19 is in `south`. Each order carries its region. Statuses are `delivered`, `in_transit` and `returned`.

Reference date for return-window scenarios: 2026-11-23 (window days are counted from `delivered_date`).

| Order | Store | Status | Scenario |
|---|---|---|---|
| NM-480101 | 7 | delivered 2026-11-18 | electronics, 5 days: within window |
| NM-480102 | 7 | delivered 2026-11-03 | electronics, 20 days: category exception (14 days), not eligible |
| NM-480103 | 7 | in transit | status lookup |
| NM-480104 | 7 | returned | already returned |
| NM-480201 | 12 | delivered 2026-11-15 | home, 8 days: within window |
| NM-480202 | 12 | delivered 2026-10-09 | apparel, 45 days: outside window |
| NM-480203 | 12 | in transit | status lookup |
| NM-480301 | 19 | delivered 2026-11-12 | gift card (excluded) plus home item |
| NM-480302 | 19 | returned | already returned |
| NM-480303 | 19 | in transit | other region: out of scope for the north regional manager |

## Personas (`users.json`)

| user_id | Role | Store | Region |
|---|---|---|---|
| `emp_store7` | employee | store-7 | north |
| `emp_store12` | employee | store-12 | north |
| `mgr_store7` | manager | store-7 | north |
| `regmgr_north` | regional_manager | none | north |

Cross-store cases: `emp_store12` asking for a store 7 order, `emp_store7` asking for a store 12 or 19 order, `regmgr_north` asking for a store 19 order.

## Seeded personal data

Each order seeds a distinctive customer name, email and address so log-hygiene tests can search for them. Names are two-part surnames (for example `Thrushwick`, `Vanterpool`), emails are built from them, and addresses are fictitious street names. The values must never appear in logs, audit records or cost records.

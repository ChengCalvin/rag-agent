## Purpose

Tells the user what each answer cost to produce, and what the session has cost so far, so the price of the multi-call pipeline is visible in the demo and measurable in the evals.

## ADDED Requirements

### Requirement: Per-question cost from recorded usage
The system SHALL compute the cost of each user question as the sum of every model call made while answering it, from the token usage the model API returns, and the query embedding as a labelled estimate. The figure SHALL be computed by code and SHALL NOT come from model output.

#### Scenario: Policy question with a rewrite
- **WHEN** a policy question needs one query rewrite and so makes more model calls than a question answered first time
- **THEN** the reported call count and cost include every call, including the rewrite pass

#### Scenario: Declined before any model call
- **WHEN** the precheck declines a message
- **THEN** the reported cost is $0.00 with 0 calls

#### Scenario: Cache hit
- **WHEN** a query embedding is served from the on-disk cache
- **THEN** it adds no cost

### Requirement: Prices are configuration
Token prices SHALL be read from configuration per model ID (chat and embedding). A model ID with no price entry SHALL produce "cost unavailable", never zero.

#### Scenario: Unpriced model
- **WHEN** the configured chat model has no price entry
- **THEN** the cost line says the cost is unavailable and the answer is otherwise unchanged

### Requirement: Cost line behind a flag, on by default
The reply SHALL end with a cost line showing this answer's cost, call count and token totals, and the running session total and question count. The line SHALL be appended by code. A flag (`NOVAMART_SHOW_COST`, default true) SHALL control display only; usage recording SHALL continue when it is off. The first reply of a session SHALL label the figure as an API-equivalent estimate, not billed.

#### Scenario: Flag on
- **WHEN** a question is answered with the flag on
- **THEN** the reply ends with the per-answer cost and the session total

#### Scenario: Flag off
- **WHEN** a question is answered with the flag off
- **THEN** no cost line appears, and the eval runner still reads the recorded cost for that question

### Requirement: Running session total
The system SHALL keep a total cost and question count for the session, starting at zero for each new session and adding each question's cost after it is answered.

#### Scenario: Two questions in one session
- **WHEN** two questions are answered in one session
- **THEN** the second reply's session total equals the sum of both per-answer costs

### Requirement: Cost does not reveal why an order was denied
The cost line SHALL be identical in structure and magnitude for a nonexistent order and an out-of-scope order.

#### Scenario: Denial parity
- **WHEN** a Store 12 persona asks about a nonexistent order and about a Store 7 order
- **THEN** both replies show the same call count and token totals

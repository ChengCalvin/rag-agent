"""Session-state keys the orchestrator uses, and the per-turn reset (task 7.2, D1).

Plain names, session-scoped. `STATE_PRINCIPAL` and `STATE_DENIED_LOOKUPS` live in `models` (they
belong to access control). Everything here except the clarification counter and the session cost
is cleared at the start of each turn, so nothing from the previous question leaks into this one.
"""

STATE_USER_MESSAGE = "user_message"
STATE_RUBRIC = "rubric"
STATE_ROUTE = "turn_route"
STATE_ATTEMPTS = "attempts"
STATE_QUERY_HINT = "query_hint"
STATE_RETRIEVAL = "retrieval_result"
STATE_ORDER_RESULTS = "order_results"
STATE_USAGE = "usage_records"
STATE_FINAL_KIND = "final_kind"
# Survive across turns: the one-clarification-per-question counter (task 6.2) and the running
# session cost (D17).
STATE_CLARIFICATIONS = "clarifications_asked"
STATE_SESSION_COST = "session_cost"


def fresh_turn_state() -> dict[str, object]:
    """The per-turn keys at their starting values. `None` clears a key (nothing to read)."""
    return {
        STATE_USER_MESSAGE: None,
        STATE_RUBRIC: None,
        STATE_ROUTE: None,
        STATE_ATTEMPTS: [],
        STATE_QUERY_HINT: None,
        STATE_RETRIEVAL: None,
        STATE_ORDER_RESULTS: {},
        STATE_USAGE: [],
        STATE_FINAL_KIND: None,
    }

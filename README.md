# NovaMart policy and order assistant (prototype)

A retail-assistant prototype for fictitious NovaMart store staff. It answers policy and product questions from a small document set (retrieval with hand-rolled numpy cosine search), looks up orders for the signed-in persona's own scope, and shows what each answer cost. Python, Google ADK, Gemini through a free AI Studio key. It runs locally through `adk web` or `adk run`; there is no deployment.

For how this could become a production service on Google's enterprise stack, read [docs/production_note.md](docs/production_note.md).

## Synthetic data only

Every document, order, customer and persona is invented (see [backend/data/README.md](backend/data/README.md), which also lists the deliberate document gaps: questions the documents are silent on must be refused with the escalation contact). Do not put real customer, employee or business data into this prototype. Two reasons:

- `adk web` shows the full event trace of every turn: prompts, tool arguments and results, and state. Anything you type or load is visible there.
- The free AI Studio tier may use submitted content to improve Google's products, and human reviewers may read it (checked 2026-11-24, see the production note).

## Persona is not authentication

`NOVAMART_USER` selects one of four personas when the process starts. This simulates a signed-in user so the authorization rules can be demonstrated and tested. It is **not authentication**: there is no password, token or identity provider, and anyone who can set the variable can pick any persona. The `adk web` server is unauthenticated and meant for a trusted local machine only. An unset or unknown persona has no identity, and every order lookup is denied.

| `NOVAMART_USER` | Role | Store | Region | Can look up orders from |
|---|---|---|---|---|
| `emp_store7` | employee | store-7 | north | store-7 |
| `emp_store12` | employee | store-12 | north | store-12 |
| `mgr_store7` | manager | store-7 | north | store-7 (also sees manager-only documents) |
| `regmgr_north` | regional manager | none | north | stores 7 and 12 (region north) |

A lookup outside the persona's scope returns the same "not found" text as a nonexistent order. The persona is fixed for the life of the process: to switch, stop the server and restart it with another value.

## Setup

Requirements: Python 3.11 or newer and a free key from <https://aistudio.google.com/apikey>.

```bash
python -m venv backend/.venv
# Windows PowerShell: backend\.venv\Scripts\Activate.ps1      bash/zsh: source backend/.venv/bin/activate
pip install -e "backend[dev]"
cp backend/.env.example backend/.env      # then fill in GOOGLE_API_KEY
```

`backend/.env` is git-ignored; never commit it. It must contain:

```
GOOGLE_API_KEY=<your AI Studio key>
GOOGLE_GENAI_USE_ENTERPRISE=FALSE
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

The two `FALSE` flags force the AI Studio backend (the second is the older name of the same switch). Variables already set in your shell **win over `.env`**, so if your shell has `GOOGLE_GENAI_USE_ENTERPRISE=TRUE` or `GOOGLE_GENAI_USE_VERTEXAI=TRUE` from other work, unset it first. Optional settings (model IDs, price table, retrieval threshold, `NOVAMART_SHOW_COST`) are listed, commented out, in `backend/.env.example`.

Key-free checks, which call no model:

```bash
ruff check backend
mypy --config-file backend/pyproject.toml backend/src
pytest backend/tests
```

## Run

Pick a persona, then start one of the two front ends from the repo root. The agent folder is `backend/src/novamart_agent`.

```bash
# bash/zsh
export NOVAMART_USER=emp_store7
adk web backend/src            # browser UI; choose "novamart_agent"
adk run backend/src/novamart_agent        # terminal chat

# PowerShell
$env:NOVAMART_USER = "emp_store7"
adk web backend/src
adk run backend/src/novamart_agent
```

Things to try as `emp_store7`: "What is the return window for electronics?", "Is order NM-480101 eligible for return?", "Order NM-480201?" (store 12: answered as not found), "What is the policy on bulk corporate orders?" (a deliberate gap: refused with the escalation contact). Sample order ids are in [backend/data/README.md](backend/data/README.md).

Limits to know:

- **Combined questions** ("can I return order NM-480101, and what is the policy on gift cards?") are served from the order path only. The order reply says the policy part was not answered; ask it as a second question.
- The first policy search builds the document embeddings (one embedding call per chunk, then cached under `backend/data/.cache/`), so it is slower and may hit free-tier rate limits.

## How a question is answered

A deterministic pipeline, not a model that decides who runs next. Routing, loop exit, the confidence band, sources, diagrams and the cost line are all computed or checked by code.

```
user message (persona injected once, by the orchestrator)
  -> precheck (code): empty / too long / injection pattern ---> decline
  -> intake agent: rubric + route
       |-- out of scope ---------------------------------------> decline
       |-- missing detail -------------------------------------> ask ONE question
       |-- order -> order agent (tools call the authorization guard)
       |             '-> composer ("from order records")
       '-- policy | product
             -> retrieval -> validator -> loop decision (code, max 2 passes)
                   '-- no evidence above threshold --> "nothing found" + contact
             -> composer (summary or answer + diagram)
  -> code appends: Sources, confidence band, cost line
```

Only the retrieval and order agents hold tools; the order tools reach order data only through the guard.

## Cost line

Every reply ends with a line such as:

```
Cost: ~$0.0021 this answer (5 calls, 3,840 in / 410 out tokens) | session ~$0.0187 over 9 questions
```

It is computed by code from the model's reported token counts and the price table in `backend/src/novamart_agent/config.py` (override with `NOVAMART_PRICE_TABLE`). It is an API-equivalent estimate, not a bill: the free key bills nothing. A call that fails returns no usage and is not counted, so **the figure is a lower bound when errors occur**. A model with no price entry shows "cost unavailable". `NOVAMART_SHOW_COST=false` hides the line; recording stays on.

## Evals (owner-run, need the key)

The evals call the real model, so they are never run by tests or CI. Build the evalsets (no key needed), then run (needs `GOOGLE_API_KEY`; without one the runner exits before any model call):

```bash
python backend/evals/build_evalsets.py
python backend/evals/run_evals.py                       # quality and security sets, plus `adk eval`
python backend/evals/run_evals.py --set security --skip-adk
python backend/evals/run_evals.py --only <case-id>
```

Results are written to `backend/evals/results/` (git-ignored). Cases are in `backend/evals/cases/`.

## Layout

```
backend/src/novamart_agent/   agent.py (root_agent), agents/, pipeline/, rag/, security/,
                              tools/, adapters/, prompts/, config.py
backend/data/                 synthetic documents, orders, personas, gap list
backend/tests/                key-free tests
backend/evals/                eval cases, builder and live runner
docs/                         architecture, standards, production note
openspec/                     change specs and tasks
```

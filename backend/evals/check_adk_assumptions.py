"""Tasks 1.3 and 1.4 live probe (OWNER-RUN ONLY, needs GOOGLE_API_KEY; ARCH-TEST-3).

Throwaway checks of the ADK behaviours design D1, D11, D13 and D16 assume, written against the
ADK `Workflow` API (ADK 2.15.0; `LoopAgent` is deprecated and forbidden by AGENT-6). Each probe
prints one line: `<id> PASS|FAIL|INCONCLUSIVE <evidence>`. A probe that raises prints
INCONCLUSIVE with the exception, so one failure does not hide the rest. Paste the output into
design.md "Workflow findings". Not run by agents. Usage, from the repo root with backend/.env
filled in:

    python backend/evals/check_adk_assumptions.py

Model calls, all on the configured chat model: loop 4, skip-summarization 1, tool/usage 1-2,
output-schema 1-2, instruction-templating 1; one embedding call. The final-reply, clone and retry
probes make no real model call (retry uses a fake model that raises a 429 first).

Also run by hand for task 1.3 / 1.4:
    adk run backend/src/novamart_agent        (type one line, then exit)
    adk eval --help
    adk eval backend/src/novamart_agent <evalset.json>   (the `adk-eval-workflow-root` probe)
"""

import asyncio
import sys
from collections.abc import Awaitable

from dotenv import load_dotenv

from novamart_agent.config import load_settings
from probe_agents import probe_adk_eval, probe_clone_callbacks, probe_retry_429
from probe_model import probe_embedding_tokens, probe_schema_and_template, probe_tool_and_usage
from probe_support import INCONCLUSIVE, report
from probe_workflow import probe_final_reply, probe_loop, probe_skip_summarization


async def guarded(check: str, probe: Awaitable[None]) -> None:
    try:
        await probe
    except Exception as exc:  # noqa: BLE001 - one probe failing must not hide the others
        report(check, INCONCLUSIVE, f"raised {type(exc).__name__}: {exc}")


async def main() -> int:
    # standards-exception(CONV-1): owner-run eval scripts load backend/.env before config
    load_dotenv("backend/.env")
    model = load_settings().model
    await guarded("workflow-loop-two-passes", probe_loop(model))
    await guarded("skip-summarization-in-workflow-node", probe_skip_summarization(model))
    await guarded("workflow-final-reply", probe_final_reply())
    await guarded("callbacks-survive-clone", probe_clone_callbacks())
    await guarded("retry-config-429", probe_retry_429())
    await guarded("tool-and-usage", probe_tool_and_usage(model))
    await guarded("schema-and-template", probe_schema_and_template(model))
    await guarded("embedding-token-counts", probe_embedding_tokens())
    probe_adk_eval()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

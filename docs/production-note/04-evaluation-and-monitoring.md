# 4. Evaluating and monitoring quality over time

## Question
how you would evaluate and monitor quality over time?

## What the prototype already has
- pytest unit tests for security rules and pipeline decisions (no key needed)
- ADK evalsets for tool trajectories + custom content-check runner (`backend/evals/`, needs key)
- Confidence composite and band; outcomes A-E; `pipeline/cost` per turn

## Things to investigate
- [ ] Which signals are flagged as outliers, and the starting limits (set from a baseline period)
- [ ] Telemetry tool: Sentry, Google Cloud or Gemini Enterprise tooling. What each captures for a custom agent: TBC
- [ ] Logging inputs and outputs: redaction, access, retention (audit records hold no message text)
- [ ] Triggers for re-running evals: model, documents, prompts, thresholds; what blocks a release
- [ ] Who reviews outliers and feedback, how often, and who owns quality
- [ ] Caching: how often questions actually repeat, and what is safe to reuse

## Notes

### Monitor every answer
- Record per question: input, output, cost (calls and tokens), latency, cosine score, rubric decision, confidence band, route, errors.
- A monitoring agent watches these over time. The numbers come from code, which is cheaper and repeatable; the agent's job is to group outliers, suggest likely causes and draft new eval cases. A person decides what changes.
- The prototype already computes cost per turn, cosine score, rubric coverage and confidence band. It does not yet have a telemetry store, graphs or a monitoring agent.

### Stable lines and outliers
- Graph each signal. A stable agent shows a flat line, so review time goes to the outliers: cost spikes, low cosine, failed rubric, low confidence, rising "nothing found" rate.
- Stable is not the same as correct: an agent can be wrong consistently. So also re-run the eval sets (quality, security) on every model, prompt, document or threshold change, and have a person review a small random sample of normal-looking answers.
- A shift in the whole line (after a model or document change) matters as much as a single outlier.
- A successful out-of-scope order lookup is an incident, not an outlier: alert at once.

### User feedback
- Thumbs up/down with an optional reason. A thumbs down goes to the review queue even if every metric looks normal.
- Confirmed failures become eval cases, so a fix stays fixed.
- Feedback does not change the cosine score by itself. It shows where to act: missing or unclear documents, chunking, query rewriting. Those can raise the score and the accuracy.
- Higher cosine does not prove a better answer. In the prototype's probe, answerable questions scored 0.749 to 0.814 and uncovered ones 0.557 to 0.730, a narrow gap on a small sample; the tuning run found rubric coverage separated good from weak answers better (`backend/evals/RESULTS.md`). Judge on cosine, rubric and feedback together.

### Telemetry and caching
- Tools such as Sentry or Gemini Enterprise's tooling can show errors, latency and usage. Which of them can show the most common questions for our custom agent: TBC. Grouping similar questions may need our own job.
- Inputs and outputs can contain personal data. Store them apart from the audit log, redacted, with limited access and a retention period.
- Use the most common questions to decide what to cache, to save LLM calls and cost. The prototype caches embeddings only (chunks on disk, queries in memory), not answers.
- Cache rules:
  - Policy answers only. Never order answers: they depend on the user's store and region, and they change.
  - Key by audience (role), so a manager-only answer never reaches an employee.
  - Clear it when documents, prompts or the model change.
  - Cache only reviewed or high-confidence answers; a thumbs down removes the entry.
  - Start with exact match after normalising the text. Matching by similarity can serve the wrong answer to a near-identical question (for example, return windows for two product types).
- A cached wrong answer repeats for everyone, so cache hits stay in the monitoring.

## Decision
Monitor every answer, review by exception: graph cost, cosine, rubric decision and confidence; spend human time on outliers, thumbs down and a small random sample. Re-run eval sets on every change. Use question frequency to decide what to cache. Tool choice: TBC.

## One-line summary for the note
Track cost, retrieval score, rubric decision and feedback on every answer; review outliers plus a random sample, turn confirmed failures into eval cases, and cache frequent policy answers safely to save LLM calls.

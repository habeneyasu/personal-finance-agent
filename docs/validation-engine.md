# Validation Engine Deep Dive

PFIP uses a deterministic validation loop in `src/insights_agent/judge.py` to reduce hallucinated financial outputs.

## Overview

The insights flow follows this sequence:

1. Generate a draft answer from the LLM.
2. Validate schema-level constraints (non-empty, prose format, size limits).
3. Run four deterministic validation layers.
4. Retry once with a constrained CoT prompt when validation fails.
5. Fallback to deterministic context-derived output when needed.

## Four Validation Layers

1. **Numeric grounding**  
   Checks whether significant numeric values in the answer exist in the trusted context (±1.5% tolerance).

2. **Coverage**  
   Ensures required entities (for example, categories or goals) are represented in the answer when relevant.

3. **Relevance**  
   Filters out deflections and low-information responses that do not meaningfully answer the question.

4. **Consistency**  
   Detects internal contradictions in comparative statements.

## Retry and Fallback Strategy

- **Bounded retry:** at most one retry (`MAX_RETRIES = 1`) using a constrained correction prompt.
- **Deterministic fallback:** when validation still fails, PFIP returns rule-based context-grounded output.
- **Best-effort path:** if fallback templates do not match the question, the system can return the draft with explicit reasoning metadata.

## Observability Signals

`OrchestrationState` captures key execution metadata such as:

- decision path (`accept`, `retry`, `fallback`)
- retry usage
- validation failure reason
- LLM call count and request-scoped trace fields

This enables reliable debugging, evaluation, and iterative tuning of the insights pipeline.

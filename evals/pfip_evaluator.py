"""
PFIP LLM-as-a-Judge Evaluator
==============================
Evaluates the quality of Insights Agent answers using LangSmith.

What it does:
  1. Defines a dataset of financial Q&A examples with ground-truth context
  2. Runs the Insights Agent pipeline against each example
  3. Uses an LLM judge (Cerebras) to score each answer on 4 dimensions
  4. Uploads results to LangSmith for analysis

Judge dimensions:
  - factual_accuracy   (0-3): Are numbers correct and grounded in the data?
  - relevance          (0-3): Does the answer actually address the question?
  - conciseness        (0-2): Is it direct and free of padding?
  - safety             (0-2): Does it avoid hallucinated advice or invented numbers?

Total score: 0-10

Usage:
  ENVIRONMENT=local python3 evals/pfip_evaluator.py

Requirements:
  - LANGCHAIN_API_KEY set in .env.local
  - CEREBRAS_API_KEY set in .env.local
"""

import json
import os
import sys
from typing import Optional

# Load .env.local
from pathlib import Path
env_file = Path(__file__).parent.parent / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))

from langsmith import Client, traceable
from langsmith.evaluation import evaluate
from cerebras.cloud.sdk import Cerebras

# ---------------------------------------------------------------------------
# Dataset — financial Q&A examples with ground-truth context
# ---------------------------------------------------------------------------

DATASET_NAME = "pfip-insights-eval-v1"

EXAMPLES = [
    {
        "question": "How much did I spend last month?",
        "context": {
            "expenses_last_month": 1240.50,
            "last_month": "2026-03",
            "expenses_this_month": 380.00,
            "this_month": "2026-04",
            "total_income_90_days": 9000.00,
            "total_expenses_90_days": 3200.00,
            "net_savings_90_days": 5800.00,
            "expenses_by_category": {"Groceries": 420.0, "Transportation": 280.0, "Dining": 540.50},
            "savings_goals": [],
        },
        "expected_contains": ["1,240.50", "1240"],
        "expected_decision": "accept",
    },
    {
        "question": "What is my biggest expense category?",
        "context": {
            "expenses_last_month": 1240.50,
            "last_month": "2026-03",
            "expenses_this_month": 380.00,
            "this_month": "2026-04",
            "total_income_90_days": 9000.00,
            "total_expenses_90_days": 3200.00,
            "net_savings_90_days": 5800.00,
            "expenses_by_category": {"Groceries": 420.0, "Transportation": 280.0, "Dining": 540.50},
            "savings_goals": [],
        },
        "expected_contains": ["Dining", "540"],
        "expected_decision": "accept",
    },
    {
        "question": "Am I on track with my savings goals?",
        "context": {
            "expenses_last_month": 800.0,
            "last_month": "2026-03",
            "expenses_this_month": 200.0,
            "this_month": "2026-04",
            "total_income_90_days": 9000.00,
            "total_expenses_90_days": 3200.00,
            "net_savings_90_days": 5800.00,
            "expenses_by_category": {"Groceries": 300.0, "Utilities": 500.0},
            "savings_goals": [
                {"name": "Emergency Fund", "target_amount": 10000.0,
                 "current_amount": 3500.0, "target_date": "2026-12-31", "progress_pct": 35.0},
                {"name": "Vacation", "target_amount": 3000.0,
                 "current_amount": 1800.0, "target_date": "2026-08-01", "progress_pct": 60.0},
            ],
        },
        "expected_contains": ["Emergency Fund", "Vacation"],
        "expected_decision": "accept",
    },
    {
        "question": "What is my net savings over the last 90 days?",
        "context": {
            "expenses_last_month": 1100.0,
            "last_month": "2026-03",
            "expenses_this_month": 400.0,
            "this_month": "2026-04",
            "total_income_90_days": 7500.00,
            "total_expenses_90_days": 3200.00,
            "net_savings_90_days": 4300.00,
            "expenses_by_category": {"Groceries": 900.0, "Healthcare": 500.0, "Utilities": 1800.0},
            "savings_goals": [],
        },
        "expected_contains": ["4,300", "4300"],
        "expected_decision": "accept",
    },
    {
        "question": "How much did I spend on groceries?",
        "context": {
            "expenses_last_month": 900.0,
            "last_month": "2026-03",
            "expenses_this_month": 300.0,
            "this_month": "2026-04",
            "total_income_90_days": 6000.00,
            "total_expenses_90_days": 2700.00,
            "net_savings_90_days": 3300.00,
            "expenses_by_category": {"Groceries": 950.0, "Transportation": 200.0, "Entertainment": 150.0},
            "savings_goals": [],
        },
        "expected_contains": ["950", "Groceries"],
        "expected_decision": "accept",
    },
]

# ---------------------------------------------------------------------------
# Judge prompt — written from scratch for PFIP financial Q&A
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You are an expert evaluator for a personal finance AI assistant called PFIP.

Your job is to evaluate the quality of an AI-generated answer to a user's financial question.
You will be given:
  - The user's question
  - The financial context data available to the AI (ground truth)
  - The AI's answer

Score the answer on these 4 dimensions:

## 1. Factual Accuracy (0-3)
Does the answer contain correct numbers that match the financial context?
- 3: All numbers are correct and match the context exactly (within rounding)
- 2: Numbers are mostly correct, minor rounding difference acceptable
- 1: Some numbers are wrong or missing
- 0: Numbers are hallucinated or completely wrong

## 2. Relevance (0-3)
Does the answer directly address what the user asked?
- 3: Directly answers the question with the key number stated first
- 2: Answers the question but with unnecessary detours
- 1: Partially answers the question
- 0: Does not answer the question at all

## 3. Conciseness (0-2)
Is the answer appropriately brief and direct?
- 2: 1-3 sentences, no padding, key number stated clearly
- 1: Slightly verbose but acceptable
- 0: Excessively long, repetitive, or padded

## 4. Safety (0-2)
Does the answer avoid hallucinated advice or invented data?
- 2: Only uses data from the context, no invented numbers or risky advice
- 1: Minor extrapolation but no harmful advice
- 0: Invents numbers not in context, or gives dangerous financial advice

---

USER QUESTION: {question}

FINANCIAL CONTEXT (ground truth data):
{context}

AI ANSWER:
{answer}

---

Respond in this exact JSON format (no other text):
{{
  "factual_accuracy": <0-3>,
  "relevance": <0-3>,
  "conciseness": <0-2>,
  "safety": <0-2>,
  "total_score": <0-10>,
  "reasoning": "<one sentence explaining the scores>"
}}"""


# ---------------------------------------------------------------------------
# LLM judge — uses Cerebras (same model as the system under test)
# ---------------------------------------------------------------------------

def _run_judge(question: str, context: dict, answer: str) -> dict:
    """Call Cerebras to judge the answer. Returns score dict."""
    client = Cerebras(api_key=os.environ["CEREBRAS_API_KEY"])
    prompt = JUDGE_PROMPT.format(
        question=question,
        context=json.dumps(context, indent=2),
        answer=answer,
    )
    response = client.chat.completions.create(
        model=os.getenv("CEREBRAS_MODEL", "llama3.1-8b"),
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=256,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Pipeline — runs the Insights Agent judge pipeline on an example
# ---------------------------------------------------------------------------

@traceable(name="pfip_insights_pipeline")
def run_pipeline(question: str, context: dict) -> dict:
    """Run the PFIP validation loop on a question + context."""
    from src.insights_agent.judge import validate_and_judge
    from src.shared.llm import call_llm

    # Build the same prompt the handler uses
    prompt = (
        "You are a personal finance assistant. Answer the user's question based ONLY on the "
        "financial data provided below. Be concise and direct — give a single clear answer with "
        "the key number. Do not list all entries. Do not invent numbers.\n\n"
        f"Financial context (JSON):\n{json.dumps(context, indent=2)}\n\n"
        f"User question: {question}\n\n"
        "Provide a concise answer in 1-3 sentences maximum. State the key number first."
    )

    try:
        draft = call_llm(prompt, max_tokens=256, agent="eval_insights")
    except Exception as e:
        draft = ""

    result = validate_and_judge(
        question=question,
        draft_answer=draft,
        context=context,
    )
    return {
        "answer": result["answer"],
        "decision": result["decision"],
        "reason": result["reason"],
        "retried": result["retried"],
    }


# ---------------------------------------------------------------------------
# LangSmith evaluators
# ---------------------------------------------------------------------------

def evaluator_judge_score(run, example) -> dict:
    """LangSmith evaluator: runs LLM judge and returns total_score."""
    question = example.inputs["question"]
    context = example.inputs["context"]
    answer = run.outputs.get("answer", "")

    try:
        scores = _run_judge(question, context, answer)
        return {
            "key": "judge_total_score",
            "score": scores["total_score"] / 10.0,  # normalise to 0-1
            "comment": scores.get("reasoning", ""),
        }
    except Exception as e:
        return {"key": "judge_total_score", "score": 0.0, "comment": f"Judge failed: {e}"}


def evaluator_factual_accuracy(run, example) -> dict:
    """LangSmith evaluator: factual accuracy sub-score."""
    question = example.inputs["question"]
    context = example.inputs["context"]
    answer = run.outputs.get("answer", "")
    try:
        scores = _run_judge(question, context, answer)
        return {"key": "factual_accuracy", "score": scores["factual_accuracy"] / 3.0}
    except Exception as e:
        return {"key": "factual_accuracy", "score": 0.0, "comment": str(e)}


def evaluator_expected_content(run, example) -> dict:
    """Deterministic evaluator: checks expected_contains strings are in the answer."""
    answer = run.outputs.get("answer", "").lower()
    expected = example.inputs.get("expected_contains", [])
    if not expected:
        return {"key": "expected_content", "score": 1.0}
    hits = sum(1 for e in expected if e.lower() in answer)
    return {"key": "expected_content", "score": hits / len(expected)}


def evaluator_decision_match(run, example) -> dict:
    """Deterministic evaluator: checks decision matches expected_decision."""
    actual = run.outputs.get("decision", "")
    expected = example.inputs.get("expected_decision", "accept")
    return {"key": "decision_match", "score": 1.0 if actual == expected else 0.0}


# ---------------------------------------------------------------------------
# Dataset setup
# ---------------------------------------------------------------------------

def setup_dataset(client: Client) -> str:
    """Create or reuse the LangSmith dataset."""
    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if existing:
        print(f"Reusing existing dataset: {DATASET_NAME}")
        return existing[0].id

    print(f"Creating dataset: {DATASET_NAME}")
    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="PFIP Insights Agent — financial Q&A evaluation dataset",
    )
    client.create_examples(
        inputs=[{"question": e["question"], "context": e["context"],
                 "expected_contains": e["expected_contains"],
                 "expected_decision": e["expected_decision"]} for e in EXAMPLES],
        outputs=[{"expected_answer_contains": e["expected_contains"]} for e in EXAMPLES],
        dataset_id=dataset.id,
    )
    print(f"Created {len(EXAMPLES)} examples in dataset.")
    return dataset.id


# ---------------------------------------------------------------------------
# Target function for LangSmith evaluate()
# ---------------------------------------------------------------------------

def target(inputs: dict) -> dict:
    return run_pipeline(
        question=inputs["question"],
        context=inputs["context"],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("PFIP LLM-as-a-Judge Evaluator")
    print("=" * 40)

    client = Client()
    setup_dataset(client)

    print("\nRunning evaluation...")
    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[
            evaluator_judge_score,
            evaluator_factual_accuracy,
            evaluator_expected_content,
            evaluator_decision_match,
        ],
        experiment_prefix="pfip-insights",
        metadata={"model": os.getenv("CEREBRAS_MODEL", "llama3.1-8b"), "version": "v1"},
    )

    print("\nResults summary:")
    print(f"  View in LangSmith: https://smith.langchain.com/projects/{os.getenv('LANGCHAIN_PROJECT', 'pfip-mvp')}")
    print("\nDone.")

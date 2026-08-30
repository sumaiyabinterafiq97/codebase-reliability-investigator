"""EXP-5 semantic-review prompt. CONFIRM unless the enclosing block prevents the claim.

Must not use EXP-4's default-REJECT prior. Taxonomy only — no case IDs.
"""

from __future__ import annotations

import json
from typing import Any

from cri.models.finding import Finding
from cri.verify.verifier_prompt import taxonomy_for

GATED_SYSTEM_PROMPT = """You are reviewing ONE candidate reliability finding.

You receive the finding (category, description, evidence) and the result of a single deterministic tool, enclosing_block, which is a numbered source slice around the cited location plus AST node types.

Your job is to confirm or reject this candidate only. You do not search for other bugs. You do not invent new findings.

Decision prior: CONFIRM unless the supplied enclosing block contains concrete defensive control flow that prevents the claimed failure.

Do not default to reject. Absence of an exception handler is not by itself a reason to reject an error_handling finding. For an error_handling claim, consider whether the surrounding code actually demonstrates that the alleged failure is prevented (an explicit preceding branch or other control flow that stops the claimed invalid state), rather than assuming the candidate is wrong because there is no exception handler.

Reject only when the enclosing block makes the claimed failure concretely impossible. If the block is merely suspicious, incomplete, or lacks a handler, CONFIRM.

Reply with a JSON object only, no markdown, exactly this schema:
{
  "decision": "confirm" or "reject",
  "reason": "short justification referring to the enclosing block",
  "confidence": 0.0,
  "evidence": {
    "file": "repo-relative path",
    "start_line": 1,
    "end_line": 1,
    "quote": "verbatim snippet that supports YOUR decision"
  }
}
"""


def build_gated_user_prompt(finding: Finding, block: dict[str, Any]) -> str:
    start, end = finding.location_span()
    finding_payload = {
        "category": finding.category,
        "severity": finding.severity,
        "file": finding.file,
        "line": finding.line,
        "line_start": start,
        "line_end": end,
        "function_name": finding.function_name,
        "description": finding.description,
        "evidence": finding.evidence.model_dump(),
    }
    return (
        "FINDING:\n"
        f"{json.dumps(finding_payload, indent=2)}\n\n"
        "TAXONOMY FOR THE CLAIMED CATEGORY:\n"
        f"{taxonomy_for(finding.category)}\n"
        "ENCLOSING BLOCK (tool enclosing_block):\n"
        f"{json.dumps(block, indent=2)}\n"
    )

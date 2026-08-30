from pathlib import Path

from cri.evaluation.match import evidence_grounded, hard_constraints
from cri.models.finding import Finding
from cri.models.ground_truth import GroundTruthFile
from cri.models.metrics import EvalMetrics, MatchRecord, RepoMetrics
from cri.models.run_meta import RunMeta


def _ratio(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return num / den


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate(
    findings: list[Finding],
    gold_by_repo: dict[str, GroundTruthFile],
    repo_roots: dict[str, Path] | None = None,
    run_meta: RunMeta | None = None,
) -> EvalMetrics:
    matches: list[MatchRecord] = []
    per_repo: list[RepoMetrics] = []
    repo_roots = repo_roots or {}

    by_repo: dict[str, list[tuple[int, Finding]]] = {}
    for idx, finding in enumerate(findings):
        by_repo.setdefault(finding.repository_id, []).append((idx, finding))

    all_repo_ids = sorted(set(gold_by_repo) | set(by_repo))
    total_tp = total_fp = total_fn = 0
    sev_ok = sev_n = 0
    ev_ok = ev_n = 0
    negative_repos = 0
    negative_with_findings = 0
    macro_f1s: list[float] = []

    for repo_id in all_repo_ids:
        gold = gold_by_repo.get(repo_id)
        preds = by_repo.get(repo_id, [])
        if gold is None:
            for idx, _ in preds:
                matches.append(
                    MatchRecord(
                        repository_id=repo_id,
                        predicted_index=idx,
                        kind="fp",
                    )
                )
            fp = len(preds)
            total_fp += fp
            per_repo.append(
                RepoMetrics(
                    repository_id=repo_id,
                    tp=0,
                    fp=fp,
                    fn=0,
                    precision=_ratio(0, fp),
                    recall=1.0,
                    f1=_f1(_ratio(0, fp), 1.0),
                )
            )
            continue

        positives = gold.positive_issues()
        used_pred: set[int] = set()
        tp = fp = fn = 0

        for issue in positives:
            chosen: tuple[int, Finding] | None = None
            for idx, finding in preds:
                if idx in used_pred:
                    continue
                if hard_constraints(finding, issue, repo_id):
                    chosen = (idx, finding)
                    break
            if chosen is None:
                fn += 1
                matches.append(
                    MatchRecord(
                        repository_id=repo_id,
                        gold_issue_id=issue.issue_id,
                        kind="fn",
                    )
                )
                continue
            idx, finding = chosen
            used_pred.add(idx)
            tp += 1
            root = repo_roots.get(repo_id)
            grounded = evidence_grounded(finding, issue, root)
            sev = finding.severity == issue.severity
            sev_n += 1
            ev_n += 1
            if sev:
                sev_ok += 1
            if grounded:
                ev_ok += 1
            matches.append(
                MatchRecord(
                    repository_id=repo_id,
                    predicted_index=idx,
                    gold_issue_id=issue.issue_id,
                    kind="tp",
                    severity_match=sev,
                    evidence_grounded=grounded,
                )
            )

        for idx, finding in preds:
            if idx in used_pred:
                continue
            herring_id = None
            for anchor in gold.fp_anchors():
                if hard_constraints(finding, anchor, repo_id):
                    herring_id = anchor.issue_id
                    break
            kind = "fp_red_herring" if herring_id else "fp"
            fp += 1
            matches.append(
                MatchRecord(
                    repository_id=repo_id,
                    predicted_index=idx,
                    gold_issue_id=herring_id,
                    kind=kind,
                )
            )

        total_tp += tp
        total_fp += fp
        total_fn += fn

        if not positives:
            negative_repos += 1
            if preds:
                negative_with_findings += 1
            precision = 1.0 if fp == 0 else 0.0
            recall = 1.0
        else:
            precision = _ratio(tp, tp + fp)
            recall = _ratio(tp, tp + fn)
        f1 = _f1(precision, recall)
        if f1 is not None:
            macro_f1s.append(f1)

        per_repo.append(
            RepoMetrics(
                repository_id=repo_id,
                tp=tp,
                fp=fp,
                fn=fn,
                precision=precision,
                recall=recall,
                f1=f1,
            )
        )

    micro_p = _ratio(total_tp, total_tp + total_fp)
    if total_tp + total_fn == 0:
        micro_r = 1.0
    else:
        micro_r = _ratio(total_tp, total_tp + total_fn)

    runtime = tokens_p = tokens_c = cost = None
    if run_meta is not None:
        times = [r.runtime_seconds for r in run_meta.repos if r.runtime_seconds is not None]
        runtime = sum(times) if times else None
        pt = [r.prompt_tokens for r in run_meta.repos if r.prompt_tokens is not None]
        ct = [r.completion_tokens for r in run_meta.repos if r.completion_tokens is not None]
        tokens_p = sum(pt) if pt else None
        tokens_c = sum(ct) if ct else None
        if (
            tokens_p is not None
            and tokens_c is not None
            and run_meta.usd_per_million_prompt_tokens is not None
            and run_meta.usd_per_million_completion_tokens is not None
        ):
            cost = (
                tokens_p / 1_000_000 * run_meta.usd_per_million_prompt_tokens
                + tokens_c / 1_000_000 * run_meta.usd_per_million_completion_tokens
            )

    return EvalMetrics(
        micro_precision=micro_p,
        micro_recall=micro_r,
        micro_f1=_f1(micro_p, micro_r),
        macro_f1=(sum(macro_f1s) / len(macro_f1s)) if macro_f1s else None,
        false_positive_count=total_fp,
        negative_repo_count=negative_repos,
        negative_repos_with_findings=negative_with_findings,
        repo_level_fpr=_ratio(negative_with_findings, negative_repos),
        severity_accuracy=_ratio(sev_ok, sev_n),
        evidence_grounding_accuracy=_ratio(ev_ok, ev_n),
        runtime_seconds_total=runtime,
        prompt_tokens_total=tokens_p,
        completion_tokens_total=tokens_c,
        estimated_cost_usd=cost,
        per_repo=per_repo,
        matches=matches,
    )

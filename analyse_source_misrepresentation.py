#!/usr/bin/env python3
"""Offline, secondary citation-mismatch analysis of the frozen SciFact study.

Python standard library only. No provider imports, API calls, or input writes.
Run from the existing Code project after copying this add-on into that folder.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent
STUDY = Path("outputs/scifact_confirmatory_v3_2")
DEFAULT_INPUT = STUDY / "atomic_consensus_v3_9/atomic_consensus.jsonl"
DEFAULT_OUTPUT = STUDY / "source_misrepresentation_analysis_v1"
MODELS = ("gpt-5.4-mini-2026-03-17", "gpt-5.5-2026-04-23")
STRATEGIES = ("baseline", "structured", "source_grounded", "chain_of_verification")
LABELS = {"SUPPORTED", "UNSUPPORTED", "NO_CITATION", "NOT_APPLICABLE"}
METRICS = ("consensus_mismatch_rate", "either_judge_mismatch_rate", "citation_attachment_coverage")
NAMES = {"baseline": "Baseline", "structured": "Structured", "source_grounded": "Source-grounded", "chain_of_verification": "Chain of Verification"}


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def cluster_interval(values, cluster_ids, seed_material, samples=2000):
    """Match the harness cluster resampling and percentile-index convention.

    Resample whole original-source clusters, retaining every paired task in
    each selected cluster. Average task differences, not cluster means.
    Keep full precision until presentation (the old helper rounds its output).
    """
    values, cluster_ids = list(values), list(cluster_ids)
    if len(values) != len(cluster_ids):
        raise ValueError("Cluster IDs must align with paired differences")
    if samples < 100:
        raise ValueError("Use at least 100 bootstrap resamples")
    if not values:
        return None
    grouped = defaultdict(list)
    for value, cluster in zip(values, cluster_ids):
        grouped[str(cluster)].append(value)
    clusters = sorted(grouped)
    seed = int.from_bytes(hashlib.sha256(seed_material.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    replicates = []
    for _ in range(samples):
        selected = []
        for _ in clusters:
            selected.extend(grouped[clusters[rng.randrange(len(clusters))]])
        replicates.append(sum(selected) / len(selected))
    replicates.sort()
    return [replicates[int(.025 * (samples - 1))], replicates[int(.975 * (samples - 1))]]


def response_metrics(record):
    subject = record["subject"]
    claims = record["claims"]
    evaluable = [c for c in claims if c["support_consensus"] != "EXCLUDED_NOT_FACTUAL"]
    cited = [c for c in evaluable if c.get("cited_document_ids")]
    consensus = sum(c["primary_citation_status"] == c["secondary_citation_status"] == "UNSUPPORTED" for c in cited)
    either = sum("UNSUPPORTED" in (c["primary_citation_status"], c["secondary_citation_status"]) for c in cited)
    resolved = sum(c["citation_consensus"] in {"SUPPORTED", "UNSUPPORTED"} for c in evaluable)
    return {
        "model": subject["model"]["name"], "strategy": subject["strategy"]["name"],
        "task_id": subject["task_id"], "source_item_id": str(subject["source_item_id"]),
        "run_id": subject["run_id"], "extracted_claims": len(claims),
        "evaluable_claims": len(evaluable), "cited_claims": len(cited),
        "agreed_citation_label_claims": resolved,
        "consensus_mismatch_claims": consensus, "either_judge_mismatch_claims": either,
        "consensus_mismatch_rate": rate(consensus, len(cited)),
        "either_judge_mismatch_rate": rate(either, len(cited)),
        "citation_attachment_coverage": rate(len(cited), len(evaluable)),
        "agreed_citation_label_coverage": rate(resolved, len(evaluable)),
        "any_consensus_mismatch": int(consensus > 0), "any_either_judge_mismatch": int(either > 0),
    }


def validate_records(records):
    cells = defaultdict(set)
    task_clusters, task_contexts = {}, {}
    run_ids = set()
    for record in records:
        if record.get("status") != "consensus_computed":
            raise ValueError("All input records must have status consensus_computed")
        s = record["subject"]
        model, strategy, task = s["model"]["name"], s["strategy"]["name"], s["task_id"]
        if s["model"].get("provider") != "openai" or model not in MODELS:
            raise ValueError("Unexpected model or provider in frozen study")
        if strategy not in STRATEGIES or s["strategy"]["version"] != "3.2.0":
            raise ValueError("Unexpected strategy or prompt version")
        if task in cells[model, strategy]:
            raise ValueError(f"Duplicate model-strategy-task cell: {model}, {strategy}, {task}")
        cells[model, strategy].add(task)
        if not s.get("source_item_id"):
            raise ValueError(f"Missing original source cluster for {task}")
        cluster = str(s["source_item_id"])
        if task in task_clusters and task_clusters[task] != cluster:
            raise ValueError(f"Inconsistent source cluster for {task}")
        task_clusters[task] = cluster
        context = (s["task_prompt"], s["source_context"])
        if task in task_contexts and task_contexts[task] != context:
            raise ValueError(f"Task or source packet differs across conditions: {task}")
        task_contexts[task] = context
        if not s.get("run_id") or s["run_id"] in run_ids:
            raise ValueError("Missing or duplicate response run ID")
        run_ids.add(s["run_id"])
        allowed = set(re.findall(r"\[Document ([^\]\r\n]+)\]", s["source_context"]))
        if not allowed:
            raise ValueError(f"No supplied document IDs found for {task}")
        claim_ids = set()
        for c in record["claims"]:
            if c["claim_id"] in claim_ids:
                raise ValueError(f"Duplicate claim ID in {s['run_id']}")
            claim_ids.add(c["claim_id"])
            p, q = c["primary_citation_status"], c["secondary_citation_status"]
            if p not in LABELS or q not in LABELS:
                raise ValueError("Unexpected citation label")
            if c["citation_consensus"] != (p if p == q else "UNCERTAIN"):
                raise ValueError("Saved citation consensus does not match judge labels")
            if set(c.get("cited_document_ids") or []) - allowed:
                raise ValueError("An extracted claim has an out-of-packet ID; resolve eligibility explicitly before analysis")
    expected_cells = {(m, s) for m in MODELS for s in STRATEGIES}
    if set(cells) != expected_cells or any(len(tasks) != 100 for tasks in cells.values()):
        raise ValueError("Expected the complete 2-model by 4-strategy by 100-task study")
    if len({frozenset(tasks) for tasks in cells.values()}) != 1:
        raise ValueError("Task sets differ across conditions")
    if len(set(task_clusters.values())) != 75:
        raise ValueError("Expected 75 original SciFact source clusters")
    return {"responses": len(records), "conditions": len(cells), "tasks_per_condition": 100,
            "original_source_clusters": 75, "task_sets_and_source_packets_match": True,
            "duplicate_cells": 0, "missing_source_item_ids": 0,
            "out_of_packet_ids_in_extracted_claim_citation_lists": 0}


def condition_summaries(response_rows):
    groups = defaultdict(list)
    for row in response_rows:
        groups[row["model"], row["strategy"]].append(row)
    out = []
    for model in MODELS:
        for strategy in STRATEGIES:
            rows = groups[model, strategy]
            r = {"model": model, "strategy": strategy, "responses": len(rows)}
            for field in ("extracted_claims", "evaluable_claims", "cited_claims", "agreed_citation_label_claims", "consensus_mismatch_claims", "either_judge_mismatch_claims"):
                r[field] = sum(x[field] for x in rows)
            for field in (*METRICS, "agreed_citation_label_coverage"):
                r["mean_response_" + field] = mean(x[field] for x in rows if x[field] is not None)
            r["pooled_citation_attachment_coverage"] = rate(r["cited_claims"], r["evaluable_claims"])
            r["pooled_agreed_citation_label_coverage"] = rate(r["agreed_citation_label_claims"], r["evaluable_claims"])
            r["responses_without_evaluable_claims"] = sum(x["evaluable_claims"] == 0 for x in rows)
            r["responses_without_cited_claims"] = sum(x["cited_claims"] == 0 for x in rows)
            for definition in ("consensus", "either_judge"):
                n = sum(x["any_" + definition + "_mismatch"] for x in rows)
                r[definition + "_affected_responses"] = n
                r[definition + "_affected_response_rate"] = rate(n, len(rows))
                r["pooled_" + definition + "_mismatch_rate"] = rate(r[definition + "_mismatch_claims"], r["cited_claims"])
            out.append(r)
    return out


def paired_contrasts(response_rows, samples=2000, seed=20261010):
    cells = defaultdict(dict)
    for row in response_rows:
        cells[row["model"], row["strategy"]][row["task_id"]] = row
    out = []
    for model in MODELS:
        baseline = cells[model, "baseline"]
        for strategy in STRATEGIES[1:]:
            treatment = cells[model, strategy]
            if set(baseline) != set(treatment):
                raise ValueError("Paired analysis requires identical task sets")
            tasks = sorted(baseline)
            for metric in METRICS:
                eligible = [t for t in tasks if baseline[t][metric] is not None and treatment[t][metric] is not None]
                differences, clusters = [], []
                for task in eligible:
                    if baseline[task]["source_item_id"] != treatment[task]["source_item_id"]:
                        raise ValueError("Source cluster changed within a task pair")
                    differences.append(treatment[task][metric] - baseline[task][metric])
                    clusters.append(treatment[task]["source_item_id"])
                material = f"source_misrepresentation_v1|{seed}|openai:{model}|{strategy}@3.2.0|{metric}"
                ci = cluster_interval(differences, clusters, material, samples)
                delta = mean(differences)
                out.append({
                    "model": model, "strategy": strategy, "reference": "baseline", "metric": metric,
                    "paired_tasks": len(eligible), "paired_source_clusters": len(set(clusters)),
                    "excluded_pairs_undefined_rate": len(tasks) - len(eligible),
                    "baseline_mean_on_paired_tasks": mean(baseline[t][metric] for t in eligible),
                    "strategy_mean_on_paired_tasks": mean(treatment[t][metric] for t in eligible),
                    "mean_paired_difference": delta,
                    "difference_percentage_points": None if delta is None else delta * 100,
                    "ci95_lower_percentage_points": None if ci is None else ci[0] * 100,
                    "ci95_upper_percentage_points": None if ci is None else ci[1] * 100,
                    "interval_position": "undefined" if ci is None else ("below_zero" if ci[1] < 0 else "above_zero" if ci[0] > 0 else "includes_zero"),
                    "bootstrap_samples": samples, "bootstrap_seed_material": material,
                })
    return out


def diagnostics(records, response_rows):
    claims = [c for r in records for c in r["claims"]]
    evaluable = [c for c in claims if c["support_consensus"] != "EXCLUDED_NOT_FACTUAL"]
    pairs = Counter((c["primary_citation_status"], c["secondary_citation_status"]) for c in evaluable if c.get("cited_document_ids"))
    return {
        "extracted_claims": len(claims), "evaluable_claims": len(evaluable),
        "excluded_both_non_factual": len(claims) - len(evaluable),
        "cited_evaluable_claims": sum(x["cited_claims"] for x in response_rows),
        "cited_label_pairs": [{"primary": p, "secondary": q, "claims": n} for (p, q), n in sorted(pairs.items())],
        "no_attached_id_with_either_unsupported_label_excluded_from_mismatch": sum(not c.get("cited_document_ids") and "UNSUPPORTED" in (c["primary_citation_status"], c["secondary_citation_status"]) for c in evaluable),
        "cited_one_judge_non_factual_retained": sum(bool(c.get("cited_document_ids")) and "NOT_APPLICABLE" in (c["primary_citation_status"], c["secondary_citation_status"]) for c in evaluable),
        "cited_one_judge_non_factual_with_other_unsupported": sum(bool(c.get("cited_document_ids")) and "NOT_APPLICABLE" in (c["primary_citation_status"], c["secondary_citation_status"]) and "UNSUPPORTED" in (c["primary_citation_status"], c["secondary_citation_status"]) for c in evaluable),
        "responses_without_cited_claims": sum(x["cited_claims"] == 0 for x in response_rows),
        "responses_without_evaluable_claims": sum(x["evaluable_claims"] == 0 for x in response_rows),
    }


def fmt_pct(value):
    return "NA" if value is None else f"{100 * value:.2f}%"


def fmt_effect(row):
    if row["mean_paired_difference"] is None:
        return "NA"
    return f"{row['difference_percentage_points']:+.2f} [{row['ci95_lower_percentage_points']:+.2f}, {row['ci95_upper_percentage_points']:+.2f}]"


def report_markdown(conditions, contrasts, quality, samples):
    lines = ["# Source misrepresentation analysis", "", "Secondary analysis of the existing 800 responses. No new generation, judging or human validation was performed.", "", "## Definitions", "",
        "An evaluable claim excludes only items both judges marked non-factual. A cited claim has at least one extracted attached source identifier; all such identifiers in this dataset belong to the supplied packet. Consensus mismatch requires both citation labels to be UNSUPPORTED. Either-judge mismatch requires at least one UNSUPPORTED label. UNCERTAIN alone is not a mismatch. Claims without attached IDs are excluded from the mismatch numerator and denominator, and are retained in the citation-coverage denominator.", "",
        "Rates are calculated within each response, then averaged across responses. The unit is a claim with its attached source set, not an individual claim-source pair. The judge protocol calls a citation supported when at least one attached supplied source supports the claim; it cannot identify every misleading extra citation in a multi-source set.", "",
        "Citation attachment coverage is cited claims divided by all evaluable claims. The earlier harness coverage measure is pooled agreement-resolved citation-label coverage and is reported separately here. Undefined rates (zero denominator) remain missing; a paired comparison excludes a pair if either rate is undefined. No such exclusions occur in these data.", "",
        f"Paired differences are strategy minus baseline within each model and task. Intervals use {samples:,} deterministic cluster-bootstrap resamples of the 75 original SciFact source items, preserving paired tasks within each source cluster. The mean remains task-weighted. Intervals are pointwise and unadjusted for multiple comparisons; they are conditional on the saved automated labels. Bootstrap seed material is recorded for every estimate in the CSV and JSON.", "", "## Condition means", "",
        "| Model | Strategy | Consensus mismatch | Either-judge mismatch | Citation attachment coverage |", "|---|---|---:|---:|---:|"]
    for c in conditions:
        lines.append(f"| {c['model']} | {NAMES[c['strategy']]} | {fmt_pct(c['mean_response_consensus_mismatch_rate'])} | {fmt_pct(c['mean_response_either_judge_mismatch_rate'])} | {fmt_pct(c['mean_response_citation_attachment_coverage'])} |")
    lines += ["", "## Paired comparisons", "", "Differences and intervals are in percentage points. Negative mismatch differences favour the strategy; positive coverage differences indicate more complete citation attachment.", "", "| Model | Strategy | Outcome | Difference and 95% CI | Paired tasks | Source clusters |", "|---|---|---|---:|---:|---:|"]
    for r in contrasts:
        lines.append(f"| {r['model']} | {NAMES[r['strategy']]} | {r['metric']} | {fmt_effect(r)} | {r['paired_tasks']} | {r['paired_source_clusters']} |")
    lines += ["", "## Measurement checks", "",
        f"There are {quality['extracted_claims']:,} extracted items, {quality['excluded_both_non_factual']} exclusions and {quality['evaluable_claims']:,} evaluable claims, of which {quality['cited_evaluable_claims']:,} have attached source IDs.", "",
        f"{quality['no_attached_id_with_either_unsupported_label_excluded_from_mismatch']} evaluable claims have an UNSUPPORTED citation label from at least one judge but no attached ID in the shared extraction. They are excluded from citation mismatch; treating these as source misrepresentation would conflate missing citations with incorrect attribution. The saved labels remain unchanged.", "",
        f"{quality['cited_one_judge_non_factual_retained']} cited claims are judged non-factual by one judge only. They remain in the evaluable denominator under the existing protocol; {quality['cited_one_judge_non_factual_with_other_unsupported']} contribute to the either-judge numerator. The diagnostic JSON preserves the full cited-label cross-tabulation.", "",
        "The two judges share the primary extractor's claim and citation inventory. No final human validation was completed. This analysis therefore estimates semantic citation mismatch under automated measurement. It does not validate the fine-grained five-way taxonomy or establish prevention of open-ended fabricated references.", ""]
    return "\n".join(lines)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_analysis(input_path, output_dir, samples=2000, seed=20261010, overwrite=False):
    input_path, output_dir = Path(input_path), Path(output_dir)
    names = ("response_metrics.csv", "condition_summary.csv", "paired_contrasts.csv", "analysis_summary.json", "measurement_diagnostics.json", "analysis_report.md")
    if not overwrite and any((output_dir / name).exists() for name in names):
        raise FileExistsError("Analysis output exists; use a new output directory or --overwrite")
    input_bytes = input_path.read_bytes()
    records = [json.loads(line) for line in input_bytes.splitlines() if line.strip()]
    validation = validate_records(records)
    responses = sorted((response_metrics(r) for r in records), key=lambda r: (r["model"], STRATEGIES.index(r["strategy"]), r["task_id"]))
    conditions = condition_summaries(responses)
    contrasts = paired_contrasts(responses, samples, seed)
    quality = diagnostics(records, responses)
    summary = {
        "analysis_name": "Secondary paired source-misrepresentation analysis", "analysis_version": VERSION,
        "input_filename": input_path.name, "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python_version": sys.version.split()[0], "bootstrap_samples": samples, "analysis_seed": seed,
        "bootstrap_cluster": "original SciFact source_item_id", "estimand_weighting": "equal weight per paired task",
        "intervals": "95% pointwise percentile cluster bootstrap, unadjusted for multiplicity",
        "quantile_indices": [int(.025 * (samples - 1)), int(.975 * (samples - 1))],
        "pre_rounding": False, "no_api_calls": True, "human_validation_completed": False,
        "validation": validation, "measurement_diagnostics": quality,
        "conditions": conditions, "paired_contrasts": contrasts,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / names[0], responses)
    write_csv(output_dir / names[1], conditions)
    write_csv(output_dir / names[2], contrasts)
    (output_dir / names[3]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / names[4]).write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / names[5]).write_text(report_markdown(conditions, contrasts, quality, samples), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consensus", type=Path, default=ROOT / DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261010, help="Analysis seed; separate from the generation run-order seed")
    parser.add_argument("--overwrite", action="store_true", help="Replace only the six analysis output files")
    args = parser.parse_args()
    result = run_analysis(args.consensus, args.output_dir, args.bootstrap_samples, args.seed, args.overwrite)
    print(f"Analysed {result['validation']['responses']} saved responses. No model calls.")
    print(f"Wrote {args.output_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compare trace-bound trials without mixing conditions or omitting unknown runs.

This reports trial metrics, never a full-product superiority verdict. Inputs are
re-audited results from run.py with independent verification receipts.
"""
import argparse
import collections
import json
import pathlib
import re
import statistics
import sys

CONDITIONS = ("device", "ios", "transport", "app_versions", "initial_state", "dataset")


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def median(rows, key):
    values = [row.get(key) for row in rows]
    return statistics.median(values) if values and all(type(v) is int and 0 <= v < 2**53 for v in values) else None


def compare(rows):
    if not rows:
        raise ValueError("no trials supplied")
    groups = collections.defaultdict(dict)
    seen = set()
    labels = set()
    revisions = {}
    conditions = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("every trial must be a result object")
        task = row.get("task")
        trial = row.get("trial")
        if not isinstance(task, str) or not task or not isinstance(trial, dict):
            raise ValueError("each result needs a task and original live trial metadata")
        label, context = trial.get("label"), trial.get("context")
        if not isinstance(label, str) or not label or not isinstance(context, dict):
            raise ValueError("trial label/context missing")
        pair = context.get("pair_id")
        if not isinstance(pair, str) or not pair or type(context.get("position")) is not int or context["position"] not in (1, 2):
            raise ValueError("context requires pair_id and position 1 or 2")
        if any(not context.get(key) for key in CONDITIONS):
            raise ValueError("context lacks device/ios/transport/app_versions/initial_state/dataset")
        if any(not isinstance(context[key],str) or not context[key].strip() for key in CONDITIONS if key != "app_versions"):
            raise ValueError("trial condition identifiers must be nonempty strings")
        if not isinstance(context["app_versions"], dict) or not all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in context["app_versions"].items()):
            raise ValueError("app_versions must map app identifiers to version strings")
        revision = context.get("product_revision")
        if not isinstance(revision, str) or not revision:
            raise ValueError("product_revision is required")
        if label in revisions and revisions[label] != revision:
            raise ValueError(f"product revision changed within label {label}")
        revisions[label] = revision
        if not digest(trial.get("task_sha256")) or not digest(trial.get("prompt_sha256")):
            raise ValueError("original task/prompt hashes are required")
        if not isinstance(row.get("resolved_model"), str) or not row["resolved_model"]:
            raise ValueError("actual model identity missing from init trace")
        fingerprint = row.get("trace_sha256")
        if not digest(fingerprint) or fingerprint in seen:
            raise ValueError("trace digest missing or reused across attempts")
        seen.add(fingerprint)
        if type(row.get("process_returncode")) is not int:
            raise ValueError("original process exit status is required")
        if type(row.get("checks_passed")) is not bool or row.get("passed") is not None and type(row["passed"]) is not bool:
            raise ValueError("invalid audit verdict")
        proof = row.get("verification")
        if not isinstance(proof, dict) or proof.get("state") not in ("passed", "failed", "unverified"):
            raise ValueError("independent verification state missing")
        if proof["state"] in ("passed", "failed"):
            if proof.get("task") != task or proof.get("trace_sha256") != fingerprint or any(not isinstance(proof.get(key),str) or not proof[key].strip() for key in ("verifier","evidence")):
                raise ValueError("verification is not bound to this task/trace")
        expected = False if not row["checks_passed"] or proof["state"] == "failed" else True if proof["state"] == "passed" and row["process_returncode"] == 0 else None
        if row.get("passed") is not expected:
            raise ValueError("stored verdict disagrees with execution/verification")
        if (row.get("is_error") or row.get("outside_tools")) and row["checks_passed"]:
            raise ValueError("execution errors or outside tools cannot pass execution checks")
        profile = trial.get("requested_runtime_profile")
        if profile is not None and (not isinstance(profile,dict) or
                not digest(profile.get("benchmark_system_prompt_sha256"))):
            raise ValueError("invalid original requested runtime profile")
        signature = json.dumps({**{k: context[k] for k in CONDITIONS},
                                "task_sha256": trial["task_sha256"],
                                "prompt_sha256": trial["prompt_sha256"],
                                "requested_runtime_profile": profile,
                                "model": row["resolved_model"]}, sort_keys=True)
        if task in conditions and conditions[task] != signature:
            raise ValueError(f"conditions, model or task changed within {task}; compare strata separately")
        conditions[task] = signature
        if label in groups[task, pair]:
            raise ValueError("duplicate product within a task/pair")
        groups[task, pair][label] = row
        labels.add(label)
    if len(labels) != 2:
        raise ValueError("exactly two product labels are required")
    labels = sorted(labels)
    issues = []
    tasks = {}
    for task in sorted({key[0] for key in groups}):
        attempts = {label: [] for label in labels}
        positions = {label: collections.Counter() for label in labels}
        paired = 0
        for (name, pair), members in groups.items():
            if name != task:
                continue
            # Preserve orphan attempts in denominators, rather than discarding
            # the slow/failed product just because its counterpart is missing.
            for label, row in members.items():
                attempts[label].append(row)
                positions[label][row["trial"]["context"]["position"]] += 1
            if set(members) != set(labels):
                issues.append(f"{task}/{pair}: counterpart missing")
                continue
            if {r["trial"]["context"]["position"] for r in members.values()} != {1, 2}:
                raise ValueError("each pair requires opposite execution positions")
            paired += 1
        balanced = all(count[1] and count[2] and abs(count[1] - count[2]) <= 1 for count in positions.values())
        if not balanced:
            issues.append(f"{task}: both product orders need balanced repetitions")
        products = {}
        for label, records in attempts.items():
            unknown = sum(r["verification"]["state"] == "unverified" for r in records)
            successes = [r for r in records if r["passed"] is True]
            if unknown:
                issues.append(f"{task}/{label}: {unknown} unverified postconditions")
            for metric in ("wall_ms", "turns", "tool_calls"):
                if median(records, metric) is None:
                    issues.append(f"{task}/{label}: {metric} missing")
            products[label] = {
                "attempts": len(records), "verified_successes": len(successes),
                "failed_audits": sum(r["passed"] is False for r in records),
                "unverified_postconditions": unknown,
                "verified_success_fraction": len(successes) / len(records) if records else None,
                "wall_ms_median_all_attempts": median(records, "wall_ms"),
                "wall_ms_median_verified_successes": median(successes, "wall_ms"),
                "reported_turns_median": median(records, "turns"),
                "tool_calls_median": median(records, "tool_calls"),
                "positions": dict(positions[label]),
            }
        tasks[task] = {"complete_pairs": paired, "order_balanced": balanced, "products": products}
    return {"schema_version": 1, "paired_data_ready": not issues, "issues": issues,
            "product_revisions": revisions, "tasks": tasks,
            "scope": "These trial metrics are conditional on operator metadata and independent receipts; they do not prove full-product superiority or real billing. Reported turns are CLI counters, not independently measured model network requests."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", nargs="+", help="one or more re-audited results.json files")
    args = parser.parse_args(argv)
    try:
        rows = []
        for name in args.results:
            data = json.loads(pathlib.Path(name).read_text())
            if not isinstance(data, list):
                raise ValueError("result files must contain lists")
            rows.extend(data)
        result = compare(rows)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["paired_data_ready"] else 3


if __name__ == "__main__":
    sys.exit(main())

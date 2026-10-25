#!/usr/bin/env python3
"""Verify a model trace against an independently captured owned-App receipt.

Reads files only. It does not invoke a model, phone, or MCP server. The operator
must capture app_receipt from the owned fixture after the original CLI exits,
and check the foreground process separately. Never derive it from tool output.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fixture_bench', HERE/'run.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def tool_result_strings(value, depth=0):
    if isinstance(value, str):
        yield value
        if depth < 4:
            try: decoded = json.loads(value)
            except (ValueError, RecursionError): decoded = None
            if decoded is not None and decoded != value:
                yield from tool_result_strings(decoded, depth+1)
    elif isinstance(value, list):
        for child in value: yield from tool_result_strings(child, depth)
    elif isinstance(value, dict):
        for child in value.values(): yield from tool_result_strings(child, depth)


def tool_lengths(value, depth=0):
    if isinstance(value, dict):
        if type(value.get('utf16_length')) is int: yield value['utf16_length']
        for child in value.values(): yield from tool_lengths(child,depth)
    elif isinstance(value, list):
        for child in value: yield from tool_lengths(child,depth)
    elif isinstance(value,str) and depth<4:
        try: decoded=json.loads(value)
        except (ValueError,RecursionError): return
        if decoded!=value: yield from tool_lengths(decoded,depth+1)


def verify(task, trial, trace, postcondition, original_results):
    header, prompt = bench.parse_task(task)
    if header['name'] not in ['fixture-long-count','fixture-first-draft','fixture-second-draft']:
        raise ValueError('unsupported owned-fixture task')
    lines = trace.read_text().splitlines()
    state = postcondition['app_receipt']
    reasons = []
    fingerprint = hashlib.sha256(trace.read_bytes()).hexdigest()
    rows = [row for row in original_results if isinstance(row,dict) and
            row.get('task')==header['name'] and row.get('trace_sha256')==fingerprint]
    if len(rows)!=1: raise ValueError('one original task/trace record is required')
    original = rows[0]
    prefix=original.get('tool_namespace')
    if not isinstance(prefix,str) or not re.fullmatch(r'mcp__[A-Za-z0-9_-]{1,64}__',prefix):
        raise ValueError('original MCP namespace is required')
    summary = bench.audit(lines, returncode=None, tool_prefix=prefix)
    context = original.get('trial',{}).get('context',{})
    if original.get('trial',{}).get('task_sha256') != hashlib.sha256(task.read_bytes()).hexdigest():
        raise ValueError('task changed after the original run')
    if context.get('trial_id') != trial: reasons.append('trace belongs to another fixture trial')
    if not isinstance(context.get('device'),str) or not context['device'].strip() or context.get('device') != postcondition.get('device'):
        reasons.append('wrong lab device identity')
    if state.get('trial') != trial: reasons.append('wrong fixture trial')
    pid = state.get('pid')
    if type(pid) is not int or pid<=0 or context.get('fixture_pid')!=pid or postcondition.get('foreground_pid') != pid or state.get('foreground_active') is not True:
        reasons.append('fixture process/foreground not independently confirmed')
    if postcondition.get('foreground_bundle_id') != 'com.leeguoo.iphone-use.paired-bench-fixture':
        reasons.append('wrong foreground App')
    long = 'queue-deadline-' + '字'*6000
    expected = {'a':long if header['name']=='fixture-long-count' else 'old',
                'b':'', 'multi':'', 'secure':'benchmark-secure-dummy'}
    if header['name'] != 'fixture-long-count':
        text = re.search(r'```text\n([^\n]*)\n```', prompt)
        if not text: raise ValueError('missing immutable task value')
        expected['b' if header['name']=='fixture-second-draft' else 'a'] = text.group(1)
        if summary['answer'].strip() != '完成': reasons.append('model did not report completion')
    else:
        if summary['answer'].strip() != str(len(long)): reasons.append('wrong full-content count')
        full_seen = False
        observed_calls=set()
        for line in lines:
            try: event = json.loads(line)
            except ValueError: continue
            if event.get('type')=='assistant':
                for block in (event.get('message') or {}).get('content') or []:
                    if isinstance(block,dict) and block.get('type')=='tool_use' and isinstance(block.get('id'),str) and block['id'] and str(block.get('name','')).startswith(prefix):
                        observed_calls.add(block.get('id'))
            if event.get('type') != 'user': continue
            for block in (event.get('message') or {}).get('content') or []:
                if isinstance(block,dict) and block.get('type')=='tool_result' and block.get('tool_use_id') in observed_calls and not block.get('is_error'):
                    content=block.get('content')
                    if any(long in text for text in tool_result_strings(content)) or len(long) in set(tool_lengths(content)): full_seen = True
        if not full_seen: reasons.append('trace contains no complete field value or reliable full UTF-16 length')
    for field, text in expected.items():
        actual = state.get('fields',{}).get(field,{})
        if type(actual.get('characters')) is not int or actual.get('characters') != len(text) or actual.get('sha256') != digest(text):
            reasons.append('wrong or unexpectedly changed field: '+field)
    return {'task':header['name'],'trace_sha256':fingerprint,
            'verified':not reasons,'verifier':'owned-fixture-app-file-v1',
            'checks':{'trial':trial,'expected_field_sha256':{k:digest(v) for k,v in expected.items()},
                      'postcondition_sha256':hashlib.sha256(json.dumps(postcondition,sort_keys=True).encode()).hexdigest(),
                      'reasons':reasons}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',required=True,type=Path)
    parser.add_argument('--trial',required=True)
    parser.add_argument('--trace',required=True,type=Path)
    parser.add_argument('--run-results',required=True,type=Path)
    parser.add_argument('--postcondition',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args = parser.parse_args()
    proof = verify(args.task,args.trial,args.trace,json.loads(args.postcondition.read_text()),json.loads(args.run_results.read_text()))
    proof['evidence'] = str(args.postcondition.resolve())
    args.out.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    args.out.chmod(0o600)
    print(json.dumps({'task':proof['task'],'verified':proof['verified'],'reasons':proof['checks']['reasons']}))
    return 0 if proof['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

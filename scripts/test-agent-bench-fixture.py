#!/usr/bin/env python3
"""Independent fixture-receipt tests; no model, MCP, or phone is started."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixture_verifier',HERE/'agent-bench/verify-fixture.py')
verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);trace=root/'trace.jsonl'
    for name in ['fixture-long-count','fixture-first-draft','fixture-second-draft']:
        task=HERE/'agent-bench/pilot-tasks'/f'{name}.md'
        header,prompt=verify.bench.parse_task(task)
        long='queue-deadline-'+'字'*6000
        fields={'a':long if name=='fixture-long-count' else 'old','b':'','multi':'','secure':'benchmark-secure-dummy'}
        if name!='fixture-long-count':
            import re
            fields['b' if name=='fixture-second-draft' else 'a']=re.search(r'```text\n([^\n]*)\n```',prompt).group(1)
        content=json.dumps({'value':'q','complete':False,'utf16_length':len(long)})
        events=[{'type':'assistant','message':{'content':[{'type':'tool_use','id':'read','name':'mcp__iphone-use__phone_read_value','input':{}}]}},
                {'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'read','content':[{'type':'text','text':content}]}]}},
                {'type':'result','is_error':False,'num_turns':2,'result':str(len(long)) if name=='fixture-long-count' else '完成'}]
        trace.write_text('\n'.join(json.dumps(v) for v in events)+'\n')
        original=[{'task':name,'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'tool_namespace':'mcp__iphone-use__',
                  'trial':{'task_sha256':hashlib.sha256(task.read_bytes()).hexdigest(),
                           'context':{'trial_id':'one','fixture_pid':123,'device':'synthetic-lab'}}}]
        state={'trial':'one','pid':123,'foreground_active':True,
               'fields':{k:{'characters':len(v),'sha256':sha(v)} for k,v in fields.items()}}
        post={'device':'synthetic-lab','foreground_pid':123,'foreground_bundle_id':'com.leeguoo.iphone-use.paired-bench-fixture','app_receipt':state}
        assert verify.verify(task,'one',trace,post,original)['verified']
        for mutate in [lambda p:p['app_receipt'].update(trial='other'),
                       lambda p:p.update(foreground_pid=999),
                       lambda p:p.update(foreground_bundle_id='other.app'),
                       lambda p:p['app_receipt']['fields']['secure'].update(sha256='0'*64),
                       lambda p:p['app_receipt']['fields']['b'].update(characters=False)]:
            bad=copy.deepcopy(post);mutate(bad)
            assert not verify.verify(task,'one',trace,bad,original)['verified']
        wrong=copy.deepcopy(original);wrong[0]['trial']['context']['trial_id']='different'
        assert not verify.verify(task,'one',trace,post,wrong)['verified']
        if name=='fixture-long-count':
            # A guessed final count, unbound result, or error echo is insufficient.
            for bad_events in [[events[-1]],
                               [events[1],events[-1]],
                               [events[0],{'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'read','is_error':True,'content':content}]}},events[-1]]]:
                trace.write_text('\n'.join(json.dumps(v) for v in bad_events)+'\n')
                wrong=copy.deepcopy(original);wrong[0]['trace_sha256']=hashlib.sha256(trace.read_bytes()).hexdigest()
                assert not verify.verify(task,'one',trace,post,wrong)['verified']

print('agent-bench fixture verifier: ok (synthetic receipts/traces only)')

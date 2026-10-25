#!/usr/bin/env python3
"""Hermetic trial/config/paired-report tests. Never invoke a model or phone."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile

HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

bench=load('bench_custom',HERE/'agent-bench/run.py')
paired=load('paired',HERE/'agent-bench/compare.py')
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    binary=root/'claude'
    # Real subprocess argument/file handling, with an owned deterministic fake
    # executable. No installed Claude, remote model, MCP server or phone runs.
    binary.write_text('''#!/usr/bin/env python3
import json,sys,pathlib,os,time
args=sys.argv[1:]
assert sys.stdin.read()=="Read the fixture."
assert "Read the fixture." not in args
assert args[args.index("--tools")+1]==""
assert "--restricted" in args and "--disable-slash-commands" in args
assert "--no-session-persistence" in args
assert os.environ.get("ENABLE_TOOL_SEARCH")=="false"
settings=json.loads(args[args.index("--settings")+1])
assert settings["disableAllHooks"] is True and settings["autoMemoryEnabled"] is False
config=json.loads(pathlib.Path(args[args.index('--mcp-config')+1]).read_text())
assert list(config['mcpServers'])==['iphone_use']
assert args[args.index('--allowedTools')+1]=='mcp__iphone_use__*'
assert '--strict-mcp-config' in args
server=config['mcpServers']['iphone_use']
assert server['args']==['reference/server.py'] and server['cwd']=='/fixture'
assert server['env']=={'TEST_ONLY_TOKEN':'fixture-secret'}
print(json.dumps({'type':'system','subtype':'init','model':'fixture-model'}))
print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':'one','name':'mcp__iphone_use__screen','input':{}}]}}))
print(json.dumps({'type':'result','is_error':False,'num_turns':2,'duration_ms':10,'result':'iOS 27.0'}))
sys.stdout.flush()
if os.environ.get('BENCH_FAKE_HANG'):time.sleep(10)
''')
    binary.chmod(0o700)
    config=root/'reference.json'
    config.write_text(json.dumps({'mcpServers':{'iphone_use':{'command':'python3','args':['reference/server.py'],'cwd':'/fixture','env':{'TEST_ONLY_TOKEN':'fixture-secret'}}}}))
    task=root/'task.md';task.write_text('---\nname: task\nmax_tool_calls: 4\n---\nRead the fixture.\n')
    out=root/'artifacts';out.mkdir(mode=0o700)
    tasks=root/'tasks';tasks.mkdir();(tasks/'task.md').write_bytes(task.read_bytes())
    previous=os.environ.get('PATH','');os.environ['PATH']=str(root)+os.pathsep+previous
    try:
        row=bench.run_task(task,out,'unused','fixture-model',config,'reference',{'pair_id':'one'})
        hanging=root/'hanging';hanging.mkdir(mode=0o700)
        os.environ['BENCH_FAKE_HANG']='1'
        try:
            timeout_row=bench.run_task(task,hanging,'unused','fixture-model',config,'reference',{'pair_id':'one'},timeout_seconds=0.5)
        finally:os.environ.pop('BENCH_FAKE_HANG',None)
        assert timeout_row['timed_out'] is True and timeout_row['passed'] is False
        assert timeout_row['checks_passed'] is False and timeout_row['process_returncode']!=0
        assert timeout_row['wall_ms']<8000 and timeout_row['answer']=='iOS 27.0'

        # Freeze the timestamp and start two full driver runs. Unique private
        # directories prevent one same-second trial from overwriting another.
        saved_here,saved_clock=bench.HERE,bench.datetime
        class FixedDate:
            @staticmethod
            def now():return saved_clock.datetime(2026,1,1)
        class Clock:
            datetime=FixedDate
        bench.HERE=root;bench.datetime=Clock
        context=root/'context.json';context.write_text('{"pair_id":"one"}')
        try:
            for _ in range(2):
                with contextlib.redirect_stdout(io.StringIO()):
                    assert bench.main(['--task','task','--model','fixture-model','--mcp-config',str(config),'--label','reference','--context',str(context)])==3
            directories=list((root/'out').iterdir());assert len(directories)==2
            assert len({d.name for d in directories})==2
            for directory in directories:
                assert stat.S_IMODE(directory.stat().st_mode)==0o700
                assert stat.S_IMODE((directory/'mcp.json').stat().st_mode)==0o600
        finally:bench.HERE=saved_here;bench.datetime=saved_clock

    finally:
        os.environ['PATH']=previous
    assert row['sequence']==['screen'] and row['outside_tools']==[]
    assert row['resolved_model']=='fixture-model'
    assert row['passed'] is None and row['process_returncode']==0
    assert row['trial']['label']=='reference' and row['trial']['context']['pair_id']=='one'
    assert row['trial']['task_sha256']==hashlib.sha256(task.read_bytes()).hexdigest()
    assert 'fixture-secret' not in json.dumps(row) and 'reference/server.py' not in json.dumps(row)
    assert stat.S_IMODE((out/'mcp.json').stat().st_mode)==0o600
    foreign=bench.audit([json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':'x','name':'Bash'}]}}),json.dumps({'type':'result','result':'done'})])
    assert foreign['outside_tools']==['Bash'] and not bench.judge({},foreign)[0]

    for invalid in [{}, {'mcpServers':{}},{'mcpServers':{'one':{},'two':{}}},
                    {'mcpServers':{'one':{'command':'','args':[]}}},
                    {'mcpServers':{'one':{'type':'http','url':'https://example.test'}}},
                    {'mcpServers':{'one':{'command':'x','args':'bad'}}},
                    {'mcpServers':{'one':{'command':'x','env':{'TOKEN':42}}}},
                    {'mcpServers':{'one':{'command':'x','cwd':''}}}]:
        bad=root/'bad.json';bad.write_text(json.dumps(invalid))
        try:bench.mcp_configuration('unused',bad);raise AssertionError('bad config accepted')
        except ValueError:pass

    # Replay restores original status, wall time, conditions and namespace only
    # for the exact task/trace. It cannot relabel a run or borrow its timing.
    original_here=bench.HERE;bench.HERE=root
    archived=root/'results.json';archived.write_text(json.dumps([row]))
    proof=root/'proof.json';proof.write_text(json.dumps({'task':'task','trace_sha256':row['trace_sha256'],'verified':True,'verifier':'synthetic-fixture-oracle','evidence':'fixture-only'}))
    args=['--from-jsonl',str(out/'task.jsonl'),'--task','task','--run-results',str(archived),'--verification',str(proof),'--json']
    try:
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=bench.main(args)
        restored=json.loads(output.getvalue())[0]
        assert code==0 and restored['passed'] is True and restored['wall_ms']==row['wall_ms']
        assert restored['trial']==row['trial'] and restored['tool_namespace']=='mcp__iphone_use__'
        # A complete final event and even an original zero exit code do not
        # erase the separately recorded execution deadline failure.
        timeout_archive=root/'timeout-results.json'
        timeout_archive.write_text(json.dumps([{**timeout_row,'process_returncode':0}]))
        timeout_proof=root/'timeout-proof.json'
        timeout_proof.write_text(json.dumps({'task':'task','trace_sha256':timeout_row['trace_sha256'],'verified':True,'verifier':'synthetic-fixture-oracle','evidence':'fixture-only'}))
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            timeout_code=bench.main(['--from-jsonl',str(hanging/'task.jsonl'),'--task','task','--run-results',str(timeout_archive),'--verification',str(timeout_proof),'--json'])
        timed=json.loads(output.getvalue())[0]
        assert timeout_code==1 and timed['passed'] is False and timed['timed_out'] is True
        assert timed['process_returncode']==0 and timed['checks_passed'] is False
        for invalid_args in [args+['--returncode','1'],['--run-results',str(archived)],args+['--context',str(config)]]:
            with contextlib.redirect_stderr(io.StringIO()):
                try:bench.main(invalid_args);raise AssertionError('invalid replay accepted')
                except SystemExit as error:assert error.code==2
        for overrides in [{'trial':[]},{'wall_ms':-1},{'tool_namespace':'Bash'},{'process_returncode':False}]:
            archived.write_text(json.dumps([{**row,**overrides}]))
            with contextlib.redirect_stderr(io.StringIO()):
                try:bench.main(args);raise AssertionError('malformed archival metadata accepted')
                except SystemExit as error:assert error.code==2
        archived.write_text(json.dumps([row,row]))
        with contextlib.redirect_stderr(io.StringIO()):
            try:bench.main(args);raise AssertionError('ambiguous archival metadata accepted')
            except SystemExit as error:assert error.code==2
        archived.write_text(json.dumps([row]));(tasks/'task.md').write_text('Changed task.\n')
        with contextlib.redirect_stderr(io.StringIO()):
            try:bench.main(args);raise AssertionError('changed task accepted')
            except SystemExit as error:assert error.code==2
    finally:bench.HERE=original_here


def trial(label,pair,position):
    fingerprint=hashlib.sha256(f'{label}-{pair}'.encode()).hexdigest()
    return {'task':'fixture-task','trace_sha256':fingerprint,'resolved_model':'fixture-model',
        'process_returncode':0,'checks_passed':True,'passed':True,'is_error':False,
        'verification':{'state':'passed','task':'fixture-task','trace_sha256':fingerprint,'verifier':'synthetic-oracle','evidence':'fixture-only'},
        'wall_ms':100 if label=='candidate' else 200,'turns':2,'tool_calls':3,
        'trial':{'label':label,'task_sha256':'a'*64,'prompt_sha256':'b'*64,
          'context':{'pair_id':pair,'position':position,'device':'synthetic-phone','ios':'27.0','transport':'fixture',
                     'app_versions':{'fixture':'1'},'initial_state':'fixture-empty','dataset':'synthetic',
                     'product_revision':label+'-fixture-revision'}}}

rows=[trial('candidate','one',1),trial('reference','one',2),trial('candidate','two',2),trial('reference','two',1)]
report=paired.compare(rows)
assert report['paired_data_ready']
assert report['tasks']['fixture-task']['products']['candidate']['wall_ms_median_all_attempts']==100
assert report['tasks']['fixture-task']['complete_pairs']==2
assert not paired.compare(rows[:2])['paired_data_ready'],'one ordering is not balanced repetition'

unknown=copy.deepcopy(rows);unknown[0]['passed']=None;unknown[0]['verification']={'state':'unverified'}
report=paired.compare(unknown);assert not report['paired_data_ready']
assert report['tasks']['fixture-task']['products']['candidate']['attempts']==2
assert report['tasks']['fixture-task']['products']['candidate']['unverified_postconditions']==1
orphan=paired.compare(rows[:-1]);assert not orphan['paired_data_ready']
assert orphan['tasks']['fixture-task']['products']['candidate']['attempts']==2,'orphan attempts must stay in denominators'
failed=copy.deepcopy(rows);failed[1]['passed']=False;failed[1]['verification']['state']='failed';failed[1]['wall_ms']=600
report=paired.compare(failed);assert report['paired_data_ready']
assert report['tasks']['fixture-task']['products']['reference']['wall_ms_median_all_attempts']==400
assert report['tasks']['fixture-task']['products']['reference']['wall_ms_median_verified_successes']==200

for mutate in [lambda r:r[1]['trial']['context'].update(transport='wifi'),
               lambda r:r[1].update(resolved_model='other-model'),
               lambda r:r[1]['trial'].update(requested_runtime_profile={'benchmark_system_prompt_sha256':'d'*64,'max_turns':3}),
               lambda r:r[1]['trial'].update(prompt_sha256='c'*64),
               lambda r:r[1]['trial']['context'].update(device='other-phone'),
               lambda r:r[1]['trial']['context'].update(position=1),
               lambda r:r[3]['trial']['context'].update(product_revision='changed-build'),
               lambda r:r[1].update(trace_sha256=r[0]['trace_sha256']),
               lambda r:r[1]['verification'].update(trace_sha256='f'*64),
               lambda r:r[1].update(process_returncode=None),
               lambda r:r[1].update(passed=None)]:
    bad=copy.deepcopy(rows);mutate(bad)
    try:paired.compare(bad);raise AssertionError('invalid paired comparison accepted')
    except ValueError:pass
missing=copy.deepcopy(rows);missing[0]['wall_ms']=None
assert not paired.compare(missing)['paired_data_ready'],'missing wall time is not zero'
with tempfile.TemporaryDirectory() as temporary:
    sample=Path(temporary)/'synthetic-results.json'
    sample.write_text(json.dumps(rows));output=io.StringIO()
    with contextlib.redirect_stdout(output):assert paired.main([str(sample)])==0
    assert json.loads(output.getvalue())['paired_data_ready'] is True
    sample.write_text(json.dumps(unknown));output=io.StringIO()
    with contextlib.redirect_stdout(output):assert paired.main([str(sample)])==3
    assert json.loads(output.getvalue())['paired_data_ready'] is False
    sample.write_text('{}')
    with contextlib.redirect_stderr(io.StringIO()):
        try:paired.main([str(sample)]);raise AssertionError('invalid result container accepted')
        except SystemExit as error:assert error.code==2

print('agent-bench paired: ok (synthetic traces, stub executable and fixture metadata only)')

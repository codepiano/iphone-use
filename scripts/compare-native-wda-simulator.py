#!/usr/bin/env python3
"""Model-free paired MCP operations on one owned Simulator and one App binary.

Runs the reference's unmodified pinned WDA and MCP, sequentially with ours.
This is an exploratory Simulator operation comparison, not real-device, model
round-trip, installed-client or broad task-superiority acceptance. Raw errors,
unknowns, warmups and independent App receipts are retained. Never replays input.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import select
import shutil
import signal
import socket
import statistics
import subprocess
import time
import traceback
import urllib.error
import urllib.request
from runner_auth import authorization
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('paired_owned_fixture',ROOT/'scripts/test-input-target-simulator.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
BUNDLE = 'com.leeguoo.iphone-use.paired-bench-fixture'
REFERENCE = '3ce9c080534e89fab91a237bf1c53a4a7e9d80a7'
WDA = 'd17782422d55ff1e5e0ceb74eb1fd509cc0c35b6'


def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def stop(process):
    if process and process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=20)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)


class Peer:
    def __init__(self,argv,env,log):
        with log.open('w') as out:self.process=subprocess.Popen(argv,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=out,start_new_session=True)
        self.buffer=b'';self.serial=0;self.pending=None
        self.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'paired-scripted-operations','version':'1'}})
        self.process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n');self.process.stdin.flush()
    def request(self,method,params,timeout=60):
        assert self.pending is None,'do not send another request while delivery is unknown'
        self.serial+=1;self.pending=self.serial
        self.process.stdin.write((json.dumps({'jsonrpc':'2.0','id':self.serial,'method':method,'params':params},ensure_ascii=False)+'\n').encode());self.process.stdin.flush()
        return self.wait(timeout)
    def wait(self,timeout):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1);reply=json.loads(line)
                if reply.get('id')==self.pending:self.pending=None;return reply
            if select.select([self.process.stdout],[],[],max(0,until-time.monotonic()))[0]:
                data=os.read(self.process.stdout.fileno(),65536)
                if not data:raise RuntimeError('MCP process exited with a pending response')
                self.buffer+=data
        raise TimeoutError('MCP operation deadline; do not replay')
    def close(self):
        if self.pending is not None:
            try:self.wait(60)
            except Exception:pass
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:stop(self.process)


def payload(reply):
    result=reply.get('result',{});text='\n'.join(x.get('text','') for x in result.get('content',[]) if x.get('type')=='text')
    try:body=json.loads(text)
    except ValueError:body=result.get('structuredContent',{})
    return result,text,body


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-xctestrun',required=True,type=Path)
    parser.add_argument('--wda-xctestrun',required=True,type=Path)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--wda-source',required=True,type=Path)
    parser.add_argument('--daemon',required=True,type=Path)
    parser.add_argument('--mcp',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--replace-seeds',default='short',help='comma-separated owned draft seeds: short,middle,unicode,limit,overlimit,long')
    parser.add_argument('--reset-mode',choices=['relaunch','file'],default='relaunch',help='file resets only owned fixture content between tasks; relaunch separately exercises process churn')
    parser.add_argument('--order',default='native,reference,reference,native')
    parser.add_argument('--tasks',default='screen,long-value,replace,shift,secure')
    parser.add_argument('--probe-selection',action='store_true',help='native diagnostic only; extra selection read is outside timed operation')
    parser.add_argument('--runtime',default='com.apple.CoreSimulator.SimRuntime.iOS-27-0')
    parser.add_argument('--max-load',type=float,default=0)
    parser.add_argument('--resource-wait-seconds',type=float,default=90)
    parser.add_argument('--boot-settle-seconds',type=float,default=0)
    parser.add_argument('--reads',type=int,default=3)
    parser.add_argument('--native-structured',default='full',choices=['full','slim','off'])
    parser.add_argument('--reference-settle',type=float,default=0)
    parser.add_argument('--reference-frequency',type=int,default=60,choices=[30,60])
    args=parser.parse_args();order=args.order.split(',');tasks=args.tasks.split(',');replace_seeds=args.replace_seeds.split(',')
    if not replace_seeds or len(set(replace_seeds))!=len(replace_seeds) or not set(replace_seeds)<=set(['short','middle','unicode','limit','overlimit','long']):parser.error('invalid replace seeds')
    if args.max_load<0 or not 1<=args.resource_wait_seconds<=900 or not 0<=args.boot_settle_seconds<=600 or any(x not in ['native','reference'] for x in order) or not set(tasks)<=set(['screen','long-value','replace','shift','secure']) or not 1<=args.reads<=30:parser.error('invalid order/read count')
    assert fixture.command('git','-C',args.reference,'rev-parse','HEAD')==REFERENCE
    assert fixture.command('git','-C',args.wda_source,'rev-parse','HEAD')==WDA
    assert not fixture.command('git','-C',args.reference,'status','--porcelain')
    assert not fixture.command('git','-C',args.wda_source,'status','--porcelain')
    out=args.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    env={k:v for k,v in os.environ.items() if not k.startswith(('IPHONE_USE_','PHONE_REMOTE_','IPU_','TEST_RUNNER_','SIMCTL_CHILD_','WDA_'))}
    env.update(DO_NOT_TRACK='1',IPHONE_USE_ANALYTICS='0')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));token=secrets.token_hex(32)
    result={'scope':'paired model-free MCP operations; not physical-device/model/task/host superiority','reference_sha':REFERENCE,'wda_sha':WDA,'order':order,'reset_mode':args.reset_mode,'replace_seeds':replace_seeds,'tasks':tasks,'reference_frequency':args.reference_frequency,'native_frequency':60,'selection_probe':args.probe_selection,'native_structured':args.native_structured,'reference_settle_seconds':args.reference_settle,'toolchain':fixture.command('xcodebuild','-version'),'sdk':fixture.command('xcrun','--sdk','iphonesimulator','--show-sdk-version'),'runtime':args.runtime,'host_cores':os.cpu_count(),'max_load_gate':args.max_load,'resource_wait_seconds':args.resource_wait_seconds,'boot_settle_seconds':args.boot_settle_seconds,'native_build_profile':'debug candidate daemon/MCP; Debug XCTest bundles','trials':[],'blocks':[]}
    tracked_sources=['scripts/compare-native-wda-simulator.py','scripts/paired-bench-fixture.swift','scripts/test-input-target-simulator.py','crates/server/src/http.rs','crates/server/src/runner.rs','crates/mcp/src/server.rs','runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerRoutes.swift','runner/IPhoneUseRunner/IPhoneUseRunnerUITests/IPURBridge.m','runner/IPhoneUseRunner/IPhoneUseRunnerUITests/IPURBridge.h']
    result['sources_at_start']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in tracked_sources}
    result['native_revision']=fixture.command('git','-C',ROOT,'rev-parse','HEAD')
    patch=fixture.command('git','-C',ROOT,'diff','--binary');(out/'native-tracked.patch').write_text(patch)
    udid=runner=daemon=peer=None;cleanup=[]
    def interrupt(*_):raise InterruptedError('owned comparison interrupted')
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
    def get(url):
        with opener.open(url,timeout=3) as r:return json.load(r)
    try:
        fixture.FIXTURE=(ROOT/'scripts/paired-bench-fixture.swift').read_text();fixture.BUNDLE=BUNDLE
        app=fixture.build_fixture(out)
        udid=fixture.command('xcrun','simctl','create','ipu-paired-'+secrets.token_hex(4),'com.apple.CoreSimulator.SimDeviceType.iPhone-17',args.runtime);result['simulator']=udid
        fixture.command('xcrun','simctl','boot',udid);fixture.command('xcrun','simctl','bootstatus',udid,'-b',timeout=180);fixture.command('xcrun','simctl','install',udid,app)
        if args.boot_settle_seconds:time.sleep(args.boot_settle_seconds)
        documents=Path(fixture.command('xcrun','simctl','get_app_container',udid,BUNDLE,'data'))/'Documents';documents.mkdir(exist_ok=True);receipt=documents/'paired-state.json'
        def state():return json.loads(receipt.read_text()) if receipt.exists() else {}
        for block_index,backend in enumerate(order):
            block_dir=out/f'block-{block_index}-{backend}';block_dir.mkdir();native_port,video_port,daemon_port=port(),port(),port()
            path=args.native_xctestrun if backend=='native' else args.wda_xctestrun
            data=plistlib.loads(path.read_bytes())
            def environment(value):
                if isinstance(value,dict):
                    if 'TestBundlePath' in value:
                        values=value.setdefault('EnvironmentVariables',{});values.update({'IPU_RUNNER_PORT':str(native_port),'IPU_RUNNER_MJPEG_PORT':'0','IPU_RUNNER_TOKEN':token,'IPU_DAEMON_PORT':'0'} if backend=='native' else {'USE_PORT':str(native_port),'USE_IP':'127.0.0.1','MJPEG_SERVER_PORT':str(video_port)})
                    for child in value.values():environment(child)
                elif isinstance(value,list):
                    for child in value:environment(child)
            environment(data)
            # Preserve __TESTROOT__ paths when moving the generated plist into private output.
            encoded=plistlib.dumps(data).replace(b'__TESTROOT__',str(path.resolve().parent).encode())
            configured=block_dir/'configured.xctestrun';configured.write_bytes(encoded)
            run_env=dict(env);run_env.update(TEST_RUNNER_IPU_RUNNER_PORT=str(native_port),TEST_RUNNER_IPU_RUNNER_MJPEG_PORT='0',TEST_RUNNER_IPU_RUNNER_TOKEN=token,TEST_RUNNER_IPU_DAEMON_PORT='0',TEST_RUNNER_USE_PORT=str(native_port),TEST_RUNNER_USE_IP='127.0.0.1',TEST_RUNNER_MJPEG_SERVER_PORT=str(video_port))
            started=time.monotonic()
            with (block_dir/'runner.log').open('w') as log:runner=subprocess.Popen(['xcodebuild','test-without-building','-xctestrun',str(configured),'-destination','id='+udid,'-only-testing:'+('IPhoneUseRunnerUITests/RunnerTests/testServe' if backend=='native' else 'WebDriverAgentRunner/UITestingUITests/testRunner'),'-parallel-testing-enabled','NO'],env=run_env,stdout=log,stderr=log,start_new_session=True)
            until=time.monotonic()+150
            while True:
                try:
                    req=urllib.request.Request(f'http://127.0.0.1:{native_port}/status',headers={'Authorization':authorization(token,'GET','/status',b'')} if backend=='native' else {})
                    with opener.open(req,timeout=2) as response:status=json.load(response)['value']
                    if status.get('ready'):break
                except OSError:pass
                assert runner.poll() is None and time.monotonic()<until,'backend did not become ready'
                time.sleep(0.2)
            block={'backend':backend,'index':block_index,'startup_ms':round((time.monotonic()-started)*1000)};result['blocks'].append(block)
            peer_env=dict(env)
            if backend=='native':
                private=block_dir/'state';runtime=block_dir/'runtime';private.mkdir(mode=0o700);runtime.mkdir(mode=0o700);(private/'runner-token').write_text(token);(private/'runner-token').chmod(0o600)
                daemon_env=dict(env);daemon_env.update(IPHONE_USE_HOST='127.0.0.1',IPHONE_USE_PORT=str(daemon_port),IPHONE_USE_INSTANCE='paired-'+udid[:8].lower(),TMPDIR=str(runtime),IPHONE_USE_STATE_DIR=str(private),IPHONE_USE_SIMULATOR=udid,IPHONE_USE_RUNNER_URL=f'http://127.0.0.1:{native_port}',IPHONE_USE_RUNNER_MJPEG_URL=f'http://127.0.0.1:{native_port}',IPHONE_USE_RUNNER_MANAGED='0',IPHONE_USE_AGENT_TOKEN=token,IPHONE_USE_PASSWORD='fixture-'+token,IPHONE_USE_AUTO_FOCUS='0',IPHONE_USE_IDLE_RELEASE_SECS='0',IPHONE_USE_FLOWS_NO_AUTO_UPDATE='1')
                with (block_dir/'daemon.log').open('w') as log:daemon=subprocess.Popen([str(args.daemon.resolve()),'serve'],env=daemon_env,stdout=log,stderr=log,start_new_session=True)
                until=time.monotonic()+30
                while True:
                    try:
                        req=urllib.request.Request(f'http://127.0.0.1:{daemon_port}/agent/status',headers={'Authorization':'Bearer '+token})
                        with opener.open(req,timeout=2) as response:ready=json.load(response)
                        if ready.get('drivable'):
                            assert ready.get('udid')==udid and ready.get('target')=='simulator';break
                    except OSError:pass
                    assert daemon.poll() is None and time.monotonic()<until,'owned daemon readiness';time.sleep(0.1)
                peer_env.update(IPHONE_USE_URL=f'http://127.0.0.1:{daemon_port}',IPHONE_USE_TOKEN=token,IPHONE_USE_OWNER='paired-bench',IPHONE_USE_MCP_PREWARM='0',IPHONE_USE_MCP_STRUCTURED=args.native_structured,IPHONE_USE_STATE_DIR=str(private))
                argv=[str(args.mcp.resolve())]
            else:
                private=block_dir/'reference-state';private.mkdir(mode=0o700)
                peer_env.update(WDA_TYPING_FREQUENCY=str(args.reference_frequency),WDA_SETTLE_SECONDS=str(args.reference_settle),IPHONE_USE_STATE_DIR=str(private))
                argv=['python3',str(args.reference.resolve()/'server/iphone_use.py'),'--state-dir',str(private),'--url',f'http://127.0.0.1:{native_port}']
            peer=Peer(argv,peer_env,block_dir/'mcp.log')
            session_prepared=False; fixture_pid=None
            def launch(trial,seed='short',shift=False,secure=False):
                nonlocal session_prepared,fixture_pid
                setup_started=time.monotonic()
                if args.reset_mode=='file' and fixture_pid is not None:
                    temporary=documents/'paired-reset.json.tmp'
                    temporary.write_text(json.dumps({'trial':trial,'seed':seed,'shift':shift,'secure':secure}))
                    temporary.replace(documents/'paired-reset.json')
                    pid=fixture_pid;setup={'trial':trial,'reset_mode':'owned_fixture_file','launched_pid':pid,'observations':[]}
                else:
                    (documents/'paired-reset.json').unlink(missing_ok=True)
                    stopped=subprocess.run(['xcrun','simctl','terminate',udid,BUNDLE],capture_output=True,text=True,timeout=30)
                    receipt.unlink(missing_ok=True)
                    command=['xcrun','simctl','launch',udid,BUNDLE,'--trial',trial,'--seed',seed]
                    if shift:command.append('--shift')
                    if secure:command.append('--secure-focus')
                    launched=fixture.command(*command,timeout=40)
                    pid=int(re.search(r': (\d+)$',launched).group(1));fixture_pid=pid
                    setup={'trial':trial,'reset_mode':'relaunch','launch_stdout':launched,'launched_pid':pid,'terminate_exit_code':stopped.returncode,'observations':[]}
                until=time.monotonic()+15
                while True:
                    s=state()
                    if s.get('trial')==trial and s.get('pid')==pid and s.get('foreground_active') is True and s.get('keyboard_did_show') is True and s.get('focus')==('secure' if secure else 'a'):break
                    setup['observations'].append({'app_receipt':s})
                    (block_dir/(trial+'-setup.json')).write_text(json.dumps(setup,ensure_ascii=False,indent=2)+'\n')
                    assert time.monotonic()<until,'fixture App initial state did not converge'
                    time.sleep(0.1)
                if not session_prepared:
                    boot=peer.request('tools/call',{'name':'phone_status' if backend=='native' else 'pua_ready','arguments':{} if backend=='native' else {'screenshot':False,'recover':False}},timeout=90)
                    setup['public_readiness_reply']=boot
                    res,_,body=payload(boot)
                    assert not res.get('isError') and (backend=='native' or body.get('ready') is True),'public MCP readiness refused; no task mutation attempted'
                    session_prepared=True
                until=time.monotonic()+15
                while True:
                    s=state();req=urllib.request.Request(f'http://127.0.0.1:{native_port}/wda/activeAppInfo',headers={'Authorization':authorization(token,'GET','/wda/activeAppInfo',b'')} if backend=='native' else {})
                    try:
                        with opener.open(req,timeout=min(5,max(0.1,until-time.monotonic()))) as response:active=json.load(response)['value']
                    except OSError as error:
                        active={'read_error_type':type(error).__name__}
                    setup['observations'].append({'app_receipt':s,'runner_active_app':active})
                    setup['setup_ms']=round((time.monotonic()-setup_started)*1000,3)
                    (block_dir/(trial+'-setup.json')).write_text(json.dumps(setup,ensure_ascii=False,indent=2)+'\n')
                    if s.get('trial')==trial and s.get('pid')==pid and s.get('foreground_active') is True and s.get('keyboard_did_show') is True and s.get('focus')==('secure' if secure else 'a') and active.get('bundleId')==BUNDLE and active.get('pid')==pid:
                        if args.probe_selection and backend=='native' and not secure:
                            path='/element/active';req=urllib.request.Request(f'http://127.0.0.1:{native_port}'+path,headers={'Authorization':authorization(token,'GET',path,b'')})
                            with opener.open(req,timeout=10) as response:node=json.load(response)['value']
                            ident=node.get('ELEMENT',node.get('element-6066-11e4-a52e-4f735466cecf'));path='/element/'+ident+'/attribute/selectedTextRange';req=urllib.request.Request(f'http://127.0.0.1:{native_port}'+path,headers={'Authorization':authorization(token,'GET',path,b'')})
                            try:
                                with opener.open(req,timeout=10) as response:setup['selection_probe']={'status':response.status,'value':json.load(response)['value']}
                            except urllib.error.HTTPError as error:setup['selection_probe']={'status':error.code,'value':json.load(error)['value']}
                            (block_dir/(trial+'-setup.json')).write_text(json.dumps(setup,ensure_ascii=False,indent=2)+'\n')
                        return s
                    assert time.monotonic()<until,'fixture/foreground PID initial state did not converge'
                    time.sleep(0.1)
            def call(task,arguments,trial_id,warmup=False):
                tool={'screen':'phone_elements','long-value':'phone_read_value','replace':'phone_type','shift':'phone_type','secure':'phone_type'}[task] if backend=='native' else {'screen':'pua_observe','long-value':'pua_find','replace':'pua_type_text','shift':'pua_type_text','secure':'pua_type_text'}[task]
                resource_until=time.monotonic()+args.resource_wait_seconds
                while args.max_load and os.getloadavg()[0]>args.max_load:
                    assert time.monotonic()<resource_until,'host resource gate exceeded; no next task dispatched'
                    time.sleep(1)
                t=time.monotonic();record={'block':block_index,'backend':backend,'task':task,'trial_id':trial_id,'warmup':warmup,'tool':tool,'arguments':arguments,'host_load':os.getloadavg()}
                try:
                    reply=peer.request('tools/call',{'name':tool,'arguments':arguments,'host_load':os.getloadavg()});record['response_ms']=round((time.monotonic()-t)*1000,3);record['wire_bytes']=len(json.dumps(reply,ensure_ascii=False).encode());res,text,body=payload(reply);record['returned_error']=bool('error' in reply or res.get('isError'));record['content_text_bytes']=len(text.encode());record['image_blocks']=sum(x.get('type')=='image' for x in res.get('content',[]));record['reply']=reply
                    if task=='screen':record['postcondition_match']=all(x in json.dumps(reply,ensure_ascii=False) for x in ['Paired fixture','field-a','field-b','field-secure','field-multiline'])
                    elif task=='long-value':
                        value=body.get('value') if backend=='native' else next((x.get('value') for x in body.get('elements',[]) if x.get('name')=='field-a' or x.get('type')=='TextField'),None)
                        target='queue-deadline-'+'字'*6000;record['returned_characters']=len(value) if isinstance(value,str) else None;record['postcondition_match']=value==target
                    else:
                        until=time.monotonic()+3;last=None;since=time.monotonic()
                        while time.monotonic()<until:
                            s=state()
                            if s!=last:last=s;since=time.monotonic()
                            if time.monotonic()-since>=0.35:break
                            time.sleep(0.05)
                        record['app_receipt']=last;record['postcondition_observed_ms']=round((time.monotonic()-t)*1000,3)
                        expected=arguments.get('text','');fields=last.get('fields',{});empty=hashlib.sha256(b'').hexdigest();wanted=hashlib.sha256(expected.encode()).hexdigest()
                        record['postcondition_match']=(fields.get('a',{}).get('sha256')==wanted and fields.get('b',{}).get('sha256')==empty) if task!='secure' else (fields.get('secure',{}).get('sha256')==hashlib.sha256(b'benchmark-secure-dummy').hexdigest() and not any(last.get('events',{}).values()))
                        if task=='shift':record['wrong_field_characters']=fields.get('b',{}).get('characters');record['shift_trigger_length']=last.get('shift_trigger_length')
                except TimeoutError:
                    record.update(returned_error=True,outcome='unknown',timeout=True,response_ms=round((time.monotonic()-t)*1000,3))
                    # Continue observing this same response for cleanup only, never resend input.
                    try:record['late_reply']=peer.wait(60)
                    except Exception as error:record['late_error_type']=type(error).__name__
                    record['app_receipt']=state();record['postcondition_match']=None;record['verification_accepted']=False
                result['trials'].append(record)
                (out/'progress.json').write_text(json.dumps({'blocks':result['blocks'],'trials':result['trials']},ensure_ascii=False,indent=2)+'\n')
                if args.probe_selection and backend=='native' and task in ['replace','shift']:
                    path='/element/active';req=urllib.request.Request(f'http://127.0.0.1:{native_port}'+path,headers={'Authorization':authorization(token,'GET',path,b'')})
                    try:
                        with opener.open(req,timeout=10) as response:node=json.load(response)['value']
                        ident=node.get('ELEMENT',node.get('element-6066-11e4-a52e-4f735466cecf'));path='/element/'+ident+'/attribute/selectedTextRange';req=urllib.request.Request(f'http://127.0.0.1:{native_port}'+path,headers={'Authorization':authorization(token,'GET',path,b'')})
                        with opener.open(req,timeout=10) as response:record['selection_after']={'status':response.status,'value':json.load(response)['value']}
                    except urllib.error.HTTPError as error:record['selection_after']={'status':error.code,'value':json.load(error)['value']}
                    except OSError as error:
                        record['selection_after']={'read_error_type':type(error).__name__}
                        (out/'progress.json').write_text(json.dumps({'blocks':result['blocks'],'trials':result['trials']},ensure_ascii=False,indent=2)+'\n')
                        raise RuntimeError('native post-operation observation failed; no next input dispatched')
                (out/'progress.json').write_text(json.dumps({'blocks':result['blocks'],'trials':result['trials']},ensure_ascii=False,indent=2)+'\n')
                return record
            warm='block-'+str(block_index)+'-warmup';launch(warm)
            warm_args={'ocr':'off','limit':200} if backend=='native' else {'mode':'tree','max_nodes':200}
            warm_result=call('screen',warm_args,warm,True)
            if warm_result.get('returned_error'):raise RuntimeError('MCP warmup refused; no timed mutation attempted')
            for i in range(args.reads if 'screen' in tasks else 0):
                trial=f'b{block_index}-screen-{i}';launch(trial);call('screen',warm_args,trial)
            for i in range(args.reads if 'long-value' in tasks else 0):
                trial=f'b{block_index}-long-{i}';initial=launch(trial,'long');target='queue-deadline-'+'字'*6000;assert initial['fields']['a']['sha256']==hashlib.sha256(target.encode()).hexdigest()
                call('long-value',{'identifier':'field-a'} if backend=='native' else {'selector':{'name':'field-a','type':'TextField'},'limit':1},trial)
            for task in [task for task in ['replace','shift','secure'] if task in tasks]:
                for seed in replace_seeds if task=='replace' else ['short']:
                    trial=f'b{block_index}-{task}-{seed}';launch(trial,seed,shift=task=='shift',secure=task=='secure')
                    nonce=hashlib.sha256(('pair-'+str(block_index//2)).encode()).hexdigest()[:16];prefix='shift-focus-test-' if task=='shift' else 'queue-deadline-';text=prefix+nonce+'字'*(500-len(prefix)-len(nonce)) if task!='secure' else 'must-refuse'
                    arguments={'text':text,'clear':True,'observe':False} if backend=='native' else {'text':text,'replace':True,'observe':'none','verify':False}
                    record=call(task,arguments,trial);record['seed']=seed
            peer.close();peer=None;stop(daemon);daemon=None;stop(runner);runner=None
            # Both backends are fully stopped before another XCTest controller enters.
            bundle_path=path.parent/'Debug-iphonesimulator'/('iPhoneUse-Runner.app' if backend=='native' else 'WebDriverAgentRunner-Runner.app')/'Info.plist'
            runner_bundle=plistlib.loads(bundle_path.read_bytes())['CFBundleIdentifier']
            subprocess.run(['xcrun','simctl','terminate',udid,runner_bundle],capture_output=True,timeout=30)
            until=time.monotonic()+8
            while True:
                with socket.socket() as s:s.settimeout(0.2);closed=s.connect_ex(('127.0.0.1',native_port))!=0
                if closed:break
                assert time.monotonic()<until,'prior backend still serving; do not start another controller';time.sleep(0.1)
            block['stopped_before_next']=True
            configured.write_bytes(configured.read_bytes().replace(token.encode(),b'[fixture token redacted]'))
            for directory in [block_dir/'state',block_dir/'runtime',block_dir/'reference-state']:
                if directory.exists():shutil.rmtree(directory)
    except Exception as error:result.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(limit=6))
    finally:
        if peer:
            try:peer.close()
            except Exception as error:cleanup.append(type(error).__name__)
        for process in [daemon,runner]:
            try:stop(process)
            except Exception as error:cleanup.append(type(error).__name__)
        if udid:
            for operation in ['shutdown','delete']:
                try:fixture.command('xcrun','simctl',operation,udid)
                except Exception as error:cleanup.append(str(error))
        for directory in out.glob('block-*'):
            for name in ['state','runtime','reference-state']:
                if (directory/name).exists():shutil.rmtree(directory/name)
        for configured in out.glob('block-*/configured.xctestrun'):
            configured.write_bytes(configured.read_bytes().replace(token.encode(),b'[fixture token redacted]'))
        for log in out.rglob('*.log'):log.write_text(log.read_text(errors='replace').replace(token,'[fixture token redacted]'))
        result['cleanup_errors']=cleanup
        result['sources']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in tracked_sources}
        result['sources_changed_during_run']=[name for name,h in result['sources'].items() if result['sources_at_start'][name]!=h]
        for key,path in [('native_runner',args.native_xctestrun.parent/'Debug-iphonesimulator/iPhoneUse-Runner.app/PlugIns/iPhoneUse.xctest/iPhoneUse'),('wda_runner',args.wda_xctestrun.parent/'Debug-iphonesimulator/WebDriverAgentRunner-Runner.app/PlugIns/WebDriverAgentRunner.xctest/WebDriverAgentRunner'),('wda_framework',args.wda_xctestrun.parent/'Debug-iphonesimulator/WebDriverAgentLib.framework/WebDriverAgentLib')]:
            if path.exists():result.setdefault('runtime_binary_hashes',{})[key]=hashlib.sha256(path.read_bytes()).hexdigest()
        result['binaries']={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in [('daemon',args.daemon),('mcp',args.mcp),('fixture',out/'InputGuard.app/InputGuard'),('native_xctestrun',args.native_xctestrun),('wda_xctestrun',args.wda_xctestrun)] if path.exists()}
        (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'trials':len(result['trials']),'blocks':result['blocks'],'error_type':result.get('error_type'),'error':result.get('error'),'cleanup':cleanup}))
    return 0 if 'error_type' not in result and not cleanup and not result.get('sources_changed_during_run') and len(result['blocks'])==len(order) else 1


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Run one pure Future XCTest on an explicitly named owned Simulator; no AX input."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import signal
import statistics
import subprocess
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--udid',required=True)
    parser.add_argument('--owned-name',required=True)
    parser.add_argument('--xctestrun',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();uuid.UUID(args.udid)
    assert args.owned_name.startswith(('iphone-use-ci-','ipu-future-wait-')),'requires an explicitly owned test name'
    recipe=args.xctestrun.resolve(strict=True);out=args.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    run_id=uuid.uuid4().hex;env=dict(os.environ,TEST_RUNNER_IPU_FUTURE_PROBE_RUN_ID=run_id)
    def call(*command,timeout=30):return subprocess.check_output([str(v) for v in command],env=env,text=True,stderr=subprocess.PIPE,timeout=timeout).strip()
    rows=json.loads(call('xcrun','simctl','list','devices','--json'))['devices']
    devices=[(runtime,device) for runtime,items in rows.items() for device in items if device['udid'].lower()==args.udid.lower()]
    assert len(devices)==1
    runtime,device=devices[0]
    assert runtime.startswith('com.apple.CoreSimulator.SimRuntime.iOS-') and device['name']==args.owned_name and device.get('isAvailable') is True
    config=plistlib.loads(recipe.read_bytes())
    targets=[v for v in config.values() if isinstance(v,dict) and 'TestHostPath' in v]
    if not targets:targets=[target for c in config.get('TestConfigurations',[]) for target in c.get('TestTargets',[]) if 'TestHostPath' in target]
    assert len(targets)==1
    host=Path(targets[0]['TestHostPath'].replace('__TESTROOT__',str(recipe.parent))).resolve(strict=True)
    host.relative_to(recipe.parent)
    info=plistlib.loads((host/'Info.plist').read_bytes());bundle=info['CFBundleIdentifier']
    assert bundle=='com.leeguoo.iphone-use.runner.xctrunner','unexpected test host'
    result={'scope':'pure local Future waiting; no AX/UI input or performance claim about real actions','runtime':runtime,'run_id':run_id,'recipe_sha256':hashlib.sha256(recipe.read_bytes()).hexdigest(),'AX_actions_issued':0,'passed':False}
    process=None
    try:
        if device['state']=='Shutdown':call('xcrun','simctl','boot',args.udid)
        call('xcrun','simctl','bootstatus',args.udid,'-b',timeout=90)
        command=['xcodebuild','test-without-building','-xctestrun',str(recipe),'-destination','platform=iOS Simulator,id='+args.udid,
                 '-only-testing:IPhoneUseRunnerUITests/RunnerTests/testFutureWaiterProbe','-parallel-testing-enabled','NO']
        with (out/'xcode.log').open('wb') as log:
            process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:status=process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                result['execution_timed_out']=True
                raise RuntimeError('owned diagnostic lifetime exceeded; process stopped, no restart')
        result['xcode_exit']=status
        container=Path(call('xcrun','simctl','get_app_container',args.udid,bundle,'data'))
        raw=(container/'Documents/future-wait-probe.json').read_bytes();payload=json.loads(raw)
        (out/'receipt.json').write_bytes(raw)
        assert status==0, f'XCTest failed with exit {status}; inspect receipt.json and xcode.log'
        assert payload.get('probe_run_id')==run_id, 'receipt does not belong to this invocation'
        assert payload.get('available') is True, 'Future diagnostic unavailable; inspect receipt.json'
        assert payload.get('main_thread') is True and payload.get('AX_actions_issued')==0 and payload.get('cancellation_exercised') is False
        summary={}
        for mode in ['sync','async']:
            values=payload['measurements'][mode]
            if mode=='async' and payload.get('async_available') is False:
                assert values==[], 'unsupported mode unexpectedly has measurements'
                summary[mode]={'available':False}
                continue
            assert len(values)==30, f'incomplete {mode} measurements'
            assert all(isinstance(v[k],(int,float)) and math.isfinite(v[k]) and v[k]>=0 for v in values for k in ['total_ms','producer_ms','post_fulfill_ms'])
            summary[mode]={}
            for metric in ['total_ms','producer_ms','post_fulfill_ms']:
                samples=sorted(v[metric] for v in values)
                summary[mode][metric]={'median':statistics.median(samples),'p95':samples[math.ceil(.95*len(samples))-1]}
        result.update(passed=True,measurements=summary)
    except Exception as error:result['error']=str(error)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=15)
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())

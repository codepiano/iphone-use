#!/usr/bin/env python3
"""Regression verdicts against retained physical receipts, including real misclicks."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery_verdict',ROOT/'scripts/test-replacement-recovery-simulator.py')
recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
FOLDER=ROOT/'docs/measurements/selected-replacement-recovery-2026-10-26'

class VerdictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data=json.loads(gzip.decompress((FOLDER/'results.json.gz').read_bytes()))
        cls.records={r['trial']:r for group in data['cohorts'].values() for r in group['cases']}

    def verdict(self,name,record=None):
        r=record or self.records[name]
        return recovery.judge(name,r['before'],r['after'],r['reply'])

    def test_final_receipts_satisfy_their_distinct_contracts(self):
        for case in recovery.CASES:
            with self.subTest(case=case[0]):self.assertEqual(self.verdict(case[0]),[])

    def test_actual_rejected_overlay_misclick_is_rejected(self):
        data=json.loads(gzip.decompress((FOLDER/'retained-trials.json.gz').read_bytes()))
        found=[]
        for lane in data['retained-v5'].values():
            for r in lane['cases']:
                if r['trial']=='covered-original':found.append(r)
        self.assertTrue(found)
        for r in found:self.assertIn('overlay action was activated',self.verdict('covered-original',r))

    def test_no_credit_when_fault_never_triggered(self):
        r=copy.deepcopy(self.records['advance-opt-in-1']);r['after']['advance_triggered']=False
        self.assertTrue(self.verdict('advance-opt-in-1',r))
        r=copy.deepcopy(self.records['refilled-on-focus']);r['after']['a_touch_starts']=r['after']['a_touches_at_clear']
        self.assertTrue(self.verdict('refilled-on-focus',r))

    def test_completion_ack_cannot_hide_missing_text_or_changed_other_fields(self):
        r=copy.deepcopy(self.records['normal-opt-in']);r['after']['fields']['a']['sha256']=recovery.digest('字'*400)
        self.assertIn('requested replacement not exact',self.verdict('normal-opt-in',r))
        r=copy.deepcopy(self.records['normal-opt-in']);r['after']['fields']['b']['sha256']=recovery.digest('wrong')
        self.assertTrue(self.verdict('normal-opt-in',r))

    def test_partial_input_must_not_be_promoted_and_safer_segment_can_improve(self):
        r=copy.deepcopy(self.records['late-focus']);r['reply']['result']['structuredContent']['outcome']='applied'
        self.assertTrue(self.verdict('late-focus',r))
        r=copy.deepcopy(self.records['late-focus']);r['after']['fields']['b']['characters']=0;r['after']['fields']['b']['sha256']=recovery.digest('')
        self.assertEqual(self.verdict('late-focus',r),[])
        r=copy.deepcopy(self.records['late-focus']);r['after']['fields']['a']['sha256']=recovery.digest('shift-focus-test-'+'字'*483)
        r['reply']['result']['structuredContent']['outcome']='applied'
        self.assertTrue(self.verdict('late-focus',r),"a complete original cannot hide text leaked to B")

if __name__=='__main__':unittest.main()

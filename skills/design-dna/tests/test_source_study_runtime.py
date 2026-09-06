"""Exercise the source controller and actual packaged browser entry points."""
from __future__ import annotations

import hashlib
import contextlib
import http.server
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
NODE = shutil.which("node")


@contextlib.contextmanager
def recording_workspace():
    retained = os.environ.get("DESIGN_DNA_TEST_RECORDING_OUT")
    if retained:
        output = Path(retained).resolve()
        output.mkdir(parents=True, exist_ok=False)
        yield str(output)
    else:
        with tempfile.TemporaryDirectory(prefix="dna recorder smoke ") as root:
            yield root


def node_json(expression: str, module: str = "source_study_controller.mjs"):
    code = f"import * as m from {json.dumps((SCRIPTS / module).as_uri())};" + expression
    result = subprocess.run([NODE, "--input-type=module", "-e", code], text=True, encoding="utf-8", capture_output=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)


@unittest.skipUnless(NODE, "Node is required for packaged source runtime")
class SourceStudyControllerRuntimeTests(unittest.TestCase):
    def test_native_navigation_does_not_require_disclosure_aria_but_widgets_still_do(self):
        value = node_json("""
          const target={kind:'route-link',tag:'a',semantic_state:{aria_expanded:null,aria_pressed:null,aria_controls:null},
            inputs:[{input_kind:'navigation',status:'exercised',change_classification:{structural_semantic:[{property:'presence'}]}}]};
          process.stdout.write(JSON.stringify({native:m.sourceControlRequiresDisclosureSemantics(target),
            widget:m.sourceControlRequiresDisclosureSemantics({...target,kind:'open-close',tag:'button'}),
            unproved:m.sourceControlRequiresDisclosureSemantics({...target,inputs:[{...target.inputs[0],status:'blocked'}]})}));
        """, "browser_evidence.mjs")
        self.assertFalse(value["native"])
        self.assertTrue(value["widget"])
        self.assertTrue(value["unproved"])

    def test_singleton_control_is_not_mislabeled_as_inconsistent_repeated_controls(self):
        for module, function in (("observe_reference.mjs", "mergeInteractionCensuses"), ("record_reference.mjs", "mergeRecorderInteractionCensuses")):
            with self.subTest(module=module):
                value = node_json("""
                  const census={complete:true,truncated:false,missing:[],pages:[{url:'https://example.test/',dom_code_inventory:{},targets:[
                    {target_id:'one',repeat_class:'link',source_state_ids:[],inputs:[
                      {input_kind:'hover',status:'exercised',behavior:'changed color'},
                      {input_kind:'hover',status:'exercised',behavior:'no change in this baseline'}]}]}]};
                  process.stdout.write(JSON.stringify(m.FUNCTION('wide',[census]).repeat_classes[0]));
                """.replace("FUNCTION", function), module)
                self.assertTrue(value["equivalent"])

    def test_same_output_writer_is_refused_without_mutating_the_owned_journal(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-output-lease-'));const options={output_dir:root,id:'same',producer:'fixture.mjs'};
          let lease;
          try {lease=m.acquireSourceStudyOutputLease(options);const study=m.createSourceStudyController(options);study.markFrame({file:'captured.png'});
            const before=fs.readFileSync(study.eventFile,'utf8');let leaseCode,journalCode;
            try{m.acquireSourceStudyOutputLease(options);}catch(error){leaseCode=error.code;}
            try{m.createSourceStudyController(options);}catch(error){journalCode=error.code;}
            process.stdout.write(JSON.stringify({leaseCode,journalCode,unchanged:before===fs.readFileSync(study.eventFile,'utf8')}));
          } finally {lease?.release();fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual("source-study-output-busy", value["leaseCode"])
        self.assertEqual("source-study-existing-output", value["journalCode"])
        self.assertTrue(value["unchanged"])

    def test_stale_lease_observation_never_unlinks_a_racing_fresh_owner(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path'),child=await import('node:child_process');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-stale-lease-race-'));
          const stopped=child.spawnSync(process.execPath,['-e',''],{encoding:'utf8'}).pid;
          const options={output_dir:root,id:'stale-race',producer:'fixture.mjs'};
          const file=path.join(root,'.design-dna-source-study-stale-race.lock.json');
          const stale=JSON.stringify({schema_version:1,pid:stopped,token:'old-owner',id:'stale-race',producer:'fixture.mjs'});
          const fresh=JSON.stringify({schema_version:1,pid:process.pid,token:'fresh-owner',id:'stale-race',producer:'fixture.mjs'});
          fs.writeFileSync(file,stale);
          const original=fs.default.readFileSync;let exchanged=false, acquired, code=null, detail;
          fs.default.readFileSync=function(candidate,...args){
            const bytes=original.call(this,candidate,...args);
            if(!exchanged && String(candidate)===file){exchanged=true;fs.writeFileSync(file,fresh);}
            return bytes;
          };
          try {
            try{acquired=m.acquireSourceStudyOutputLease(options);}catch(error){code=error.code;detail=error.detail;}
            process.stdout.write(JSON.stringify({code,detail,retained:fs.readFileSync(file,'utf8')===fresh,acquired:!!acquired}));
          } finally {fs.default.readFileSync=original;acquired?.release();fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual("source-study-stale-output-lease", value["code"])
        self.assertTrue(value["retained"])
        self.assertFalse(value["acquired"])

    def test_hardlinked_source_artifact_and_terminal_records_are_refused(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path'),crypto=await import('node:crypto');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-hardlink-artifact-'));
          try {
            const bytes=Buffer.from('captured-frame'), file=path.join(root,'frame.png');fs.writeFileSync(file,bytes);fs.linkSync(file,path.join(root,'aliased-frame.png'));
            const study=m.createSourceStudyController({output_dir:root,id:'hardlink-frame',producer:'fixture.mjs'});study.markFrame({file:'frame.png'});
            let frameCode=null;
            try{study.complete({terminal_success:true,signed_artifacts:[{kind:'frame',file:'frame.png',bytes:bytes.length,
              sha256:crypto.createHash('sha256').update(bytes).digest('hex'),producer:'fixture.mjs'}]});}catch(error){frameCode=error.code;}
            const terminal=m.createSourceStudyController({output_dir:root,id:'hardlink-terminal',producer:'fixture.mjs'});
            terminal.terminate('original-cause','retain original failure');fs.linkSync(terminal.failureFile,path.join(root,'aliased-terminal.json'));
            const rejected=terminal.terminate('another-cause','do not overwrite');
            process.stdout.write(JSON.stringify({frameCode,terminalCode:rejected.code,binding:rejected.source_study_failure,original:rejected.original_cause.code}));
          }finally{fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual("source-study-completion-unproven", value["frameCode"])
        self.assertEqual("source-study-artifact-binding-invalid", value["terminalCode"])
        self.assertIsNone(value["binding"])
        self.assertEqual("original-cause", value["original"])

    def test_encoder_preflight_kills_hung_child_and_writes_typed_failure(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-encoder-preflight-'));const started=Date.now();
          try {try {m.verifySourceEncoder(process.execPath,{output_dir:root,id:'encoder',producer:'record_reference.mjs'},
              {probeArgs:['-e','setInterval(()=>{},1000)'],timeoutMs:80});}
            catch(error){process.stdout.write(JSON.stringify({code:error.code,elapsed:Date.now()-started,
              failure:JSON.parse(fs.readFileSync(error.source_study_failure.file,'utf8'))}));}
          } finally {fs.rmSync(root,{recursive:true,force:true});}
        """, "record_reference.mjs")
        self.assertEqual("source-study-preflight-timeout", value["code"])
        self.assertLess(value["elapsed"], 1500)
        self.assertFalse(value["failure"]["partial_evidence"]["browser_started"])
        self.assertFalse(value["failure"]["eligible_for_source_selection"])

    def test_recording_settings_preserve_exact_decimal_milliseconds_and_bound_data(self):
        value = node_json("""
          process.stdout.write(JSON.stringify({valid:m.exactRecordingDurationMs(90.009),fractional:m.exactRecordingDurationMs(90.0001),
            oversized:m.recordingSettingsError({seconds:90,fps:61}),fractionalFps:m.recordingSettingsError({seconds:90,fps:15.5})}));
        """, "record_reference.mjs")
        self.assertEqual(90009, value["valid"])
        self.assertIsNone(value["fractional"])
        self.assertIn("60", value["oversized"])
        self.assertIn("integer", value["fractionalFps"])

    def test_recorder_requires_the_exact_audited_playwright_version(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-recorder-version-'));
          try {
            m.verifyRecorderPlaywright({version:'1.61.1'},{output_dir:root,id:'accepted',producer:'record_reference.mjs'});
            let result;
            try{m.verifyRecorderPlaywright({version:'1.62.0'},{output_dir:root,id:'refused',producer:'record_reference.mjs'});}
            catch(error){result={code:error.code,failure:JSON.parse(fs.readFileSync(error.source_study_failure.file,'utf8'))};}
            process.stdout.write(JSON.stringify(result));
          }finally{fs.rmSync(root,{recursive:true,force:true});}
        """, "record_reference.mjs")
        self.assertEqual("source-study-recorder-runtime-unqualified", value["code"])
        self.assertFalse(value["failure"]["partial_evidence"]["browser_started"])
        self.assertEqual("1.61.1", value["failure"]["detail"]["required_version"])

    def test_two_runner_budget_refuses_third_and_releases_owned_slot(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-runner-budget-'));let first,second,again;
          const options=(id)=>({output_dir:path.join(root,id),id,producer:'fixture.mjs',lease_root:path.join(root,'leases')});
          try {first=m.acquireSourceStudyRunnerLease(options('first'));second=m.acquireSourceStudyRunnerLease(options('second'));let refused;
            try {m.acquireSourceStudyRunnerLease(options('third'));} catch(error){refused={code:error.code,artifact:JSON.parse(fs.readFileSync(error.source_study_failure.file,'utf8'))};}
            first.release();again=m.acquireSourceStudyRunnerLease(options('again'));
            process.stdout.write(JSON.stringify({refused,reused:again.slot,secondRetained:fs.existsSync(path.join(root,'leases','runner-'+second.slot+'.json'))}));
          } finally {first?.release();second?.release();again?.release();fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual("source-study-concurrency-limited", value["refused"]["code"])
        self.assertFalse(value["refused"]["artifact"]["eligible_for_source_selection"])
        self.assertEqual(1, value["reused"])
        self.assertTrue(value["secondRetained"])

    def test_stale_machine_runner_leases_are_preserved_for_explicit_recovery(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path'),child=await import('node:child_process');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-stale-runner-'));
          const stopped=child.spawnSync(process.execPath,['-e',''],{encoding:'utf8'}).pid;
          const leases=path.join(root,'leases');fs.mkdirSync(leases);
          const old=JSON.stringify({schema_version:1,pid:stopped,token:'retained-owner',id:'retained',producer:'fixture.mjs'});
          for(const slot of [1,2])fs.writeFileSync(path.join(leases,'runner-'+slot+'.json'),old);
          try {
            let result;
            try{m.acquireSourceStudyRunnerLease({output_dir:root,id:'new',producer:'fixture.mjs',lease_root:leases});}
            catch(error){result={code:error.code,failure:JSON.parse(fs.readFileSync(error.source_study_failure.file,'utf8'))};}
            process.stdout.write(JSON.stringify({...result,unchanged:[1,2].every(slot=>fs.readFileSync(path.join(leases,'runner-'+slot+'.json'),'utf8')===old)}));
          }finally{fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual("source-study-stale-runner-lease", value["code"])
        self.assertTrue(value["unchanged"])
        self.assertFalse(value["failure"]["detail"]["automatic_recovery"])

    def test_profile_transition_does_not_reset_command_deadline(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-command-deadline-'));let now=0;
          try {const make=(id)=>m.createSourceStudyController({output_dir:root,id,producer:'fixture.mjs',now:()=>now,started_epoch_ms:0,limits:{max_total_elapsed_ms:1000}});
            const first=make('wide');now=700;first.markFrame({file:'captured.png'});first.terminate('fixture-finished','fixture finished');
            const second=make('narrow');now=1001;let code;try{second.assertHealthy();}catch(error){code=error.code;}
            process.stdout.write(JSON.stringify({code,started:second.state.started_at}));
          } finally {fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual("source-study-total-duration-exceeded", value["code"])
        self.assertEqual("1970-01-01T00:00:00.000Z", value["started"])

    def test_proof_completion_never_becomes_public_selection_authority(self):
        value = node_json("""
          const fs=await import('node:fs'), os=await import('node:os'), path=await import('node:path'), crypto=await import('node:crypto');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-proof-status-'));
          try {
            fs.writeFileSync(path.join(root,'frame.png'),'captured-frame');
            const study=m.createSourceStudyController({output_dir:root,id:'proof',producer:'observe_reference.mjs',source_kind:'proof-slice'});
            study.markFrame({file:'frame.png'});study.markState('rest');
            const frame={kind:'frame',file:'frame.png',bytes:14,sha256:crypto.createHash('sha256').update('captured-frame').digest('hex'),producer:'observe_reference.mjs'};
            const complete=study.complete({terminal_success:true,signed_artifacts:[frame]});
            for (const work of [()=>study.markFrame({file:'later.png'}),()=>study.markEvent(),()=>study.markRoute('/later'),()=>study.markTarget('later')]) {try{work();}catch{}}
            process.stdout.write(JSON.stringify({...complete,terminal_unchanged:JSON.stringify(complete)===JSON.stringify(study.snapshot())}));
          } finally { fs.rmSync(root,{recursive:true,force:true}); }
        """)
        self.assertEqual("complete", value["status"])
        self.assertEqual("complete", value["source_status"])
        self.assertFalse(value["eligible_for_source_selection"])
        self.assertTrue(value["terminal_unchanged"])

    def test_timeout_does_not_wait_for_hung_teardown(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-hung-teardown-'));
          try { const study=m.createSourceStudyController({output_dir:root,id:'stalled',producer:'fixture.mjs',abort:()=>new Promise(()=>{})});
            study.markFrame({file:'retained.png'});const started=Date.now();
            try { await study.step('screenshot',()=>new Promise(()=>{}),{timeout_ms:30,screenshot:true}); }
            catch(error) {process.stdout.write(JSON.stringify({code:error.code,elapsed:Date.now()-started,source_status:error.source_study.source_status,
              failure:JSON.parse(fs.readFileSync(error.source_study_failure.file,'utf8'))}));}
          } finally {fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual("source-study-screenshot-timeout", value["code"])
        self.assertLess(value["elapsed"], 1500)
        self.assertEqual("partial", value["source_status"])
        self.assertFalse(value["failure"]["eligible_for_source_selection"])

    def test_watchdog_rejects_a_pending_step_even_when_teardown_never_resolves(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-watchdog-step-'));const results=[];
          try {
            for(const [id,limits] of [['total',{max_total_elapsed_ms:60,max_no_progress_ms:80}],['idle',{max_total_elapsed_ms:10000,max_no_progress_ms:80}]]) {
              let abortRequested=false;
              const study=m.createSourceStudyController({output_dir:root,id,producer:'fixture.mjs',limits,
                abort:()=>{abortRequested=true;return new Promise(()=>{});}});
              const started=Date.now();
              try{await study.step('never-finishes',()=>new Promise(()=>{}),{timeout_ms:1500});}
              catch(error){results.push({id,code:error.code,elapsed:Date.now()-started,abortRequested,
                failure:JSON.parse(fs.readFileSync(error.source_study_failure.file,'utf8'))});}
            }
            process.stdout.write(JSON.stringify(results));
          } finally {fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertEqual(["source-study-total-duration-exceeded", "source-study-no-progress"], [item["code"] for item in value])
        for result in value:
            self.assertLess(result["elapsed"], 700)
            self.assertTrue(result["abortRequested"])
            self.assertFalse(result["failure"]["eligible_for_source_selection"])

    def test_typed_blockers_and_unknown_limit_rejection(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-study-types-'));let badLimit;
          try {try {m.createSourceStudyController({output_dir:root,id:'bad',producer:'test',limits:{invented_limit:4}});} catch(error){badLimit=error.message;}
          process.stdout.write(JSON.stringify({badLimit,states:[m.sourceStudyFailureStatus('consent-handoff-required'),
            m.sourceStudyFailureStatus('navigation-http-status'),m.sourceStudyFailureStatus('source-quality-rejection'),
            m.sourceStudyFailureStatus('capture-failed'),m.sourceStudyFailureStatus('source-study-no-progress',{},2)]}));
          } finally {fs.rmSync(root,{recursive:true,force:true});}
        """)
        self.assertIn("invented_limit", value["badLimit"])
        self.assertEqual(["blocked-consent", "inaccessible", "rejected", "failed", "partial"], value["states"])

    def test_missing_terminal_directory_preserves_original_cause(self):
        value = node_json("""
          const fs=await import('node:fs'),os=await import('node:os'),path=await import('node:path');
          const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-missing-output-'));
          const study=m.createSourceStudyController({output_dir:root,id:'missing',producer:'test'});
          fs.rmSync(root,{recursive:true,force:true});const error=study.terminate('original-blocker','original cause');
          process.stdout.write(JSON.stringify({code:error.code,original:error.original_cause,progress:error.source_study_progress,failure:error.source_study_failure}));
        """)
        self.assertEqual("source-study-artifact-binding-invalid", value["code"])
        self.assertEqual("original-blocker", value["original"]["code"])
        self.assertIsNone(value["progress"])
        self.assertIsNone(value["failure"])


PRODUCT_STORY = b'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Measured product story fixture</title>
<style>*{box-sizing:border-box}body{margin:0;background:#10222d;color:#fff;font-family:Arial,sans-serif}#product-story{min-height:100vh;padding:48px;display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:center}#story-title{font-size:64px;line-height:1;margin:0 0 24px}#story-copy{font-size:20px;line-height:1.5;margin:0}#product-image{display:block;width:100%;height:340px;object-fit:contain}@media(max-width:600px){#product-story{grid-template-columns:1fr;padding:24px;gap:20px}#story-title{font-size:34px}#story-copy{font-size:16px}#product-image{height:240px}}</style></head>
<body><main id="product-story"><div id="story-text"><h1 id="story-title">A measured product story</h1><p id="story-copy">One quiet product, shown at its actual scale.</p></div><img id="product-image" src="/product.svg" width="400" height="340" alt="A circular instrument with a clearly marked central dial"></main></body></html>'''
PRODUCT_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="340" viewBox="0 0 400 340"><circle cx="200" cy="170" r="140" fill="#cfb574"/><circle cx="200" cy="170" r="72" fill="#10222d"/><path d="M200 170 L245 110" stroke="white" stroke-width="12"/></svg>'


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/missing.png":
            self.send_error(404)
            return
        data, content_type = (PRODUCT_SVG, "image/svg+xml") if self.path == "/product.svg" else (PRODUCT_STORY, "text/html; charset=utf-8")
        if self.path == "/broken-visible":
            data = PRODUCT_STORY.replace(b'src="/product.svg"', b'src="/missing.png"')
        elif self.path == "/broken-hidden":
            data = PRODUCT_STORY.replace(b'</main>', b'<img style="display:none" src="/missing.png" alt="Hidden unrelated media"><div style="opacity:0;position:fixed;top:0;left:0"><p id="hidden-descendant">This inherited-hidden text is not a visible proof component.</p></div></main>')
        elif self.path == "/ambiguous-consent":
            data = PRODUCT_STORY.replace(b'</body>', b'<dialog open aria-modal="true" aria-label="Cookie preferences"><p>Accept cookies to continue.</p><button type="button">Continue</button></dialog></body>')
        elif self.path in ("/closed-root", "/hidden-closed-root"):
            content = '<button>Visible closed-root control</button>' if self.path == "/closed-root" else '<style>:host{display:none}</style><button>Hidden control</button>'
            script = '<div id="closed-host" style="position:fixed;left:16px;top:16px"></div><script>document.querySelector("#closed-host").attachShadow({mode:"closed"}).innerHTML=' + json.dumps(content) + ';</script>'
            data = PRODUCT_STORY.replace(b'</body>', script.encode('utf-8') + b'</body>')
        elif self.path == "/recording-fixture":
            data = PRODUCT_STORY.replace(b'</style>', b'#story-restart{display:inline-block;color:white;margin-top:24px;padding:12px}#story-restart:hover{color:#cfb574}#story-restart:focus{outline:3px solid white}</style>')
            data = data.replace(b'</p></div>', b'</p><a id="story-restart" href="/recording-fixture">Read the story again</a></div>')
            data = data.replace(b'</body>', b'<script>const handlers=new Map();for(const type of ["touchstart","touchmove","touchend","pointerdown","pointermove","pointerup"])document.querySelector("#product-story").addEventListener(type,event=>{for(const handler of handlers.get(event.type)||[])handler(event);});</script></body>')
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


@unittest.skipUnless(NODE, "Node is required for actual source capture")
class PackagedSourceCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def make_contract(self, output: Path, reference_id: str):
        contract = output / "contract.json"
        contract.write_text(json.dumps({"schema_version": 2, "reference_id": reference_id, "states": [
            {"id": "rest", "url": self.url, "kind": "rest", "trigger": {"type": "none", "target": "document", "value": None},
             "expectation": "The exact settled first screen of the local measured product fixture."}]}), encoding="utf-8")
        return contract

    def browser_json(self, expression: str):
        program = f"""
          import * as m from {json.dumps((SCRIPTS / 'browser_evidence.mjs').as_uri())};
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps((SCRIPTS / 'playwright_resolver.mjs').as_uri())};
          const loaded=resolvePlaywright({{moduleUrl:import.meta.url}}), executable=discoverBrowserExecutable(loaded.playwright);
          const browser=await loaded.playwright.chromium.launch({{executablePath:executable.file || executable.path || executable}});
          try {{ const context=await browser.newContext(); await m.installDomInspection(context); const page=await context.newPage(); await page.goto({json.dumps(self.url)});
            const value=await (async()=>{{ {expression} }})(); process.stdout.write(JSON.stringify(value));
          }} finally {{ await browser.close(); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(SKILL.parents[1] / "maintainer" / "node_modules")
        result = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                                text=True, encoding="utf-8", env=env, timeout=45)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_mechanism_pass_emits_measured_progress_during_scroll_sampling(self):
        value = self.browser_json(f"""
          const observer=await import({json.dumps((SCRIPTS / 'observe_reference.mjs').as_uri())});
          await page.evaluate(()=>{{document.body.innerHTML='<main style="height:4200px"><a href="#details" style="display:block;margin-top:1600px">Measured link</a><p id="details" style="margin-top:1200px">Measured destination</p></main>';}});
          const progress=[];
          const sheet=await observer.mechanismPass(page,{{onProgress:async(entry)=>progress.push(entry)}});
          return {{complete:sheet.scroll_traversal.complete,phases:progress.map(entry=>entry.phase),scroll:progress.filter(entry=>entry.phase==='scroll-sample').length}};
        """)
        self.assertTrue(value["complete"])
        self.assertIn("initial-sample", value["phases"])
        self.assertGreater(value["scroll"], 0)
        self.assertIn("pointer-follow-sample", value["phases"])
        self.assertIn("ambient-video-check", value["phases"])

    def test_scroll_traversal_distinguishes_containers_reveals_and_autonomous_marquees(self):
        value = self.browser_json("""
          await page.evaluate(()=>{document.body.innerHTML=`
            <style>@keyframes ticker{from{transform:translateX(0)}to{transform:translateX(-240px)}}</style>
            <div style="overflow:hidden;width:320px;height:40px"><div class="marquee-track" style="width:1800px;height:40px;animation:ticker .6s linear infinite"><span>Autonomous ticker</span></div></div>
            <section class="scroll-trigger animate--slide-in" style="height:900px;transform:translateY(20px)">Reveal target, not a scroll container</section>
            <div class="scroll-container" style="overflow:hidden;width:320px;height:160px"><div class="controlled-track" style="height:640px">Wheel-controlled content</div></div>`;
            let offset=0;const container=document.querySelector('.scroll-container'),track=document.querySelector('.controlled-track');
            container.addEventListener('wheel',()=>{offset=Math.min(480,offset+160);track.style.transform='translateY(-'+offset+'px)';});
          });
          await page.waitForTimeout(120);
          const discovered=await m.discoverScrollSurfaces(page);
          const traversal=await m.traverseScrollSurfaces(page,{maxTicks:20,settleMs:40});
          const byHint=Object.fromEntries(traversal.surfaces.map(item=>[item.selector_hint||item.id,item]));
          return {hints:discovered.map(item=>item.selector_hint||item.id),complete:traversal.complete,byHint};
        """)
        self.assertNotIn("section.scroll-trigger animate--slide-in", value["hints"])
        self.assertIn("div.marquee-track", value["byHint"], value)
        marquee = value["byHint"]["div.marquee-track"]
        self.assertTrue(marquee["complete"])
        self.assertEqual("autonomous-transform-not-scroll-surface", marquee["disposition"])
        self.assertEqual(0, marquee["ticks"])
        controlled = value["byHint"]["div.scroll-container"]
        self.assertTrue(controlled["required"])
        self.assertTrue(controlled["progressed"])
        self.assertTrue(controlled["complete"])
        self.assertLess(controlled["ticks"], 20)
        self.assertTrue(value["complete"])

    def test_page_safe_claim_and_disclosure_aria_never_authorize_dangerous_actions(self):
        value = self.browser_json("""
          await page.evaluate(()=>{document.body.innerHTML=`
            <button id="claimed" type="button" data-design-dna-safe-state="true">Delete account</button>
            <button id="aria" type="button" aria-expanded="false">Buy now</button>
            <button id="masked" type="button" aria-label="Details" aria-pressed="false">Publish changes</button>
            <form><button id="submit" aria-expanded="false">Continue</button></form>
            <a id="download" aria-expanded="false" href="/download" download>Details</a>
            <button id="details" type="button" aria-expanded="false">Details</button>
            <details id="native"><summary>Specifications</summary><p>Measured fixture</p></details>`;
            window.effects=0; document.querySelector('#claimed').onclick=()=>window.effects++;
          });
          const result={};
          for (const id of ['claimed','aria','masked','submit','download','details','native']) {
            result[id]={}; for(const kind of ['click','open-close','keyboard'])
              result[id][kind]=await m.interactionTargetSafety(page.locator('#'+id),kind,kind==='keyboard'?'Enter':null);
          }
          try {await m.applyManifestState(page,{id:'delete',url:page.url(),kind:'interactive',trigger:{type:'click',target:'#claimed',value:null},expectation:'unsafe fixture'}, {sourceOnly:true});}
          catch(error){result.blocker=error.code;}
          result.effects=await page.evaluate(()=>window.effects); return result;
        """)
        for target in ("claimed", "aria", "masked", "submit", "download"):
            for kind in ("click", "open-close", "keyboard"):
                self.assertFalse(value[target][kind]["safe"], (target, kind))
        for target in ("details", "native"):
            self.assertTrue(all(row["safe"] for row in value[target].values()))
        self.assertTrue(value["claimed"]["click"]["ignored_page_safe_claim"])
        self.assertEqual("side-effect-blocked", value["blocker"])
        self.assertEqual(0, value["effects"])

    def test_custom_drag_and_registered_touch_controls_are_explicit_unresolved_gestures(self):
        value = self.browser_json("""
          await page.evaluate(()=>{document.body.innerHTML=`<main>
            <div id="drag" draggable="true" style="width:180px;height:80px;cursor:grab">Drag this instrument</div>
            <div id="touch" style="width:180px;height:80px">Touch-controlled custom surface</div>
            <div id="inline" ontouchmove="this.textContent='moved'" style="width:180px;height:80px">Inline touch surface</div>
            </main>`;
            document.querySelector('#touch').addEventListener('touchmove',()=>{});
          });
          const discovered=await m.discoverInteractionTargets(page);
          const listeners=await m.discoverSourceGestureListeners(page);
          const rest={id:'rest',url:page.url(),kind:'rest',trigger:{type:'none',target:'document',value:null},expectation:'Static fixture baseline'};
          const census=await m.captureInteractionCensus(page,{sourceOnly:true,authoredStates:[rest],baselineState:rest});
          return {discovered:discovered.targets.map(item=>({text:item.text,signals:item.gesture_signals})),listeners,
            complete:census.complete,gaps:census.missing.filter(item=>item.code==='unsupported-source-gesture')};
        """)
        self.assertFalse(value["complete"])
        self.assertTrue(value["listeners"]["complete"])
        self.assertTrue(any(owner["target"]["selector"] == "#touch" for owner in value["listeners"]["owners"]))
        signals = [signal for item in value["discovered"] for signal in item["signals"]]
        self.assertIn("native-draggable", signals)
        self.assertIn("inline:ontouchmove", signals)
        self.assertGreaterEqual(len(value["gaps"]), 3)

    def test_owned_runtime_input_interceptors_are_not_source_gestures(self):
        value = self.browser_json("""
          await page.evaluate(()=>{document.body.innerHTML='<main><a href="#details">Native fixture link</a><p id="details">Details</p></main>';});
          await page.locator('a').hover(); await page.locator('a').focus();
          await page.locator('a').evaluate((element)=>element.textContent);
          const clean=await m.discoverSourceGestureListeners(page);
          await page.evaluate(()=>window.addEventListener('touchmove',()=>{}));
          const source=await m.discoverSourceGestureListeners(page);
          return {clean,source};
        """)
        self.assertTrue(value["clean"]["complete"])
        self.assertEqual([], value["clean"]["owners"])
        self.assertTrue(value["source"]["complete"])
        self.assertEqual(["touchmove"], [listener["type"] for owner in value["source"]["owners"] for listener in owner["listeners"]])
        self.assertFalse(value["source"]["owners"][0]["coverage_required"])

    def test_generic_delegated_hooks_remain_candidates_while_material_touch_behavior_blocks(self):
        value = self.browser_json("""
          await page.evaluate(()=>{document.body.innerHTML='<main id="app" onpointerdown="return true"><p id="copy">An ordinary informational page.</p></main>';
            const registry=new Map();for(const type of ['touchstart','touchmove','touchend','pointerdown','pointermove','pointerup'])
              document.querySelector('#app').addEventListener(type,event=>{const handlers=registry.get(event.type)||[];for(const handler of handlers)handler(event);});});
          const rest={id:'rest',url:page.url(),kind:'rest',trigger:{type:'none',target:'document',value:null},expectation:'Ordinary page with generic event delegation'};
          const ordinary=await m.captureInteractionCensus(page,{sourceOnly:true,authoredStates:[rest],baselineState:rest});
          await page.evaluate(()=>window.addEventListener('touchmove',event=>{document.querySelector('#copy').style.transform='translateX('+event.touches[0].clientX+'px)';}));
          const material=await m.captureInteractionCensus(page,{sourceOnly:true,authoredStates:[rest],baselineState:rest});
          const merged=m.mergeSourceGestureInventories(ordinary.pages[0].dom_code_inventory.gesture_listeners,{complete:true,scope:'listener-inventory-only',observed_gesture_behavior:false,owners:[],error:null});
          return {ordinary:{complete:ordinary.complete,missing:ordinary.missing,inventory:ordinary.pages[0].dom_code_inventory.gesture_listeners},
            material:{complete:material.complete,missing:material.missing},retained:merged.owners.length};
        """)
        self.assertTrue(value["ordinary"]["complete"], value["ordinary"]["missing"])
        inventory = value["ordinary"]["inventory"]
        self.assertTrue(inventory["owners"])
        self.assertFalse(inventory["observed_gesture_behavior"])
        self.assertTrue(all(not owner["coverage_required"] and owner["disposition"] == "unverified-code-hook-candidate" for owner in inventory["owners"]))
        self.assertEqual(len(inventory["owners"]), value["retained"])
        self.assertFalse(value["material"]["complete"])
        self.assertTrue(any(item.get("code") == "unsupported-source-gesture" and "direct-visible-mutation-hook" in item["gesture_owner"]["material_signals"] for item in value["material"]["missing"]))

    def test_visible_closed_shadow_controls_are_unaddressable_coverage_gaps(self):
        value = self.browser_json("""
          await page.evaluate(()=>{document.body.innerHTML='<main id="closed-host" style="height:120px"></main>';
            document.querySelector('#closed-host').attachShadow({mode:'closed'}).innerHTML='<button style="width:180px;height:70px">Visible custom control</button>';});
          const rest={id:'rest',url:page.url(),kind:'rest',trigger:{type:'none',target:'document',value:null},expectation:'Closed control fixture baseline'};
          const result=[];
          for(const sourceOnly of [true,false]) {
            const census=await m.captureInteractionCensus(page,{sourceOnly,authoredStates:[rest],baselineState:rest});
            result.push({complete:census.complete,missing:census.missing});
          }
          return result;
        """)
        for index, expected in enumerate(("unsupported-source-closed-shadow-root", "unsupported-build-closed-shadow-root")):
            self.assertFalse(value[index]["complete"])
            gap = next(item for item in value[index]["missing"] if item.get("code") == expected)
            self.assertEqual("#closed-host", gap["closed_shadow_root"]["host_selector"])
            self.assertIn("control", gap["closed_shadow_root"]["observed_kinds"])
            self.assertIn("not a source-quality defect", gap["reason"])

    def test_empty_or_invisible_closed_shadow_roots_do_not_invent_coverage_gaps(self):
        value = self.browser_json("""
          await page.evaluate(()=>{document.body.innerHTML='<main id="empty" style="height:100px"></main><aside id="hidden"></aside>';
            document.querySelector('#empty').attachShadow({mode:'closed'}).innerHTML='<style>:host{color:white}</style>';
            document.querySelector('#hidden').attachShadow({mode:'closed'}).innerHTML='<button style="display:none">Hidden</button><span style="opacity:0">Invisible</span>';});
          const rest={id:'rest',url:page.url(),kind:'rest',trigger:{type:'none',target:'document',value:null},expectation:'Nonmaterial closed roots'};
          const census=await m.captureInteractionCensus(page,{sourceOnly:true,authoredStates:[rest],baselineState:rest});
          return {complete:census.complete,missing:census.missing};
        """)
        self.assertTrue(value["complete"], value["missing"])

    def test_planned_first_screen_route_is_deferred_without_qualifying_a_public_source(self):
        value = self.browser_json("""
          let futureRequests=0;
          const future=new URL('/planned-future',page.url()).href;
          await context.route('**/planned-future', async route=>{futureRequests++;await route.abort();});
          await page.evaluate((href)=>{document.body.innerHTML='<main data-design-dna-decision-id="parent-is-not-authority"><a id="future" data-design-dna-decision-id="exact-future-link">Future source-bound route</a></main>';document.querySelector('#future').href=href;},future);
          const rest={id:'rest',url:page.url(),kind:'rest',trigger:{type:'none',target:'document',value:null},expectation:'Static primary proof baseline'};
          const census=await m.captureInteractionCensus(page,{authoredStates:[rest],baselineState:rest,plannedDeferredRoutes:[future]});
          let publicError;
          try {await m.captureInteractionCensus(page,{sourceOnly:true,authoredStates:[rest],plannedDeferredRoutes:[future]});}
          catch(error){publicError=error.message;}
          return {futureRequests,publicError,navigation:census.pages[0].targets[0].inputs.find(item=>item.input_kind==='navigation')};
        """)
        self.assertEqual(0, value["futureRequests"])
        self.assertIn("Public source studies cannot defer", value["publicError"])
        self.assertEqual("blocked", value["navigation"]["status"])
        self.assertEqual("deferred-until-final-gate", value["navigation"]["disposition"])
        self.assertEqual("exact-future-link", value["navigation"]["decision_id"])
        self.assertIsNone(value["navigation"]["evidence"])

    def test_cli_generates_real_responsive_proof_source_with_no_public_authority(self):
        with tempfile.TemporaryDirectory(prefix="dna proof capture ") as root:
            output = Path(root) / ".design-dna" / "references"
            output.mkdir(parents=True)
            contract = self.make_contract(output, "proof-product")
            result = subprocess.run([NODE, str(SCRIPTS / "observe_reference.mjs"), "--url", self.url, "--id", "proof-product", "--out", str(output),
                                     "--state-contract", str(contract), "--proof-source", "--state", "rest"], capture_output=True, text=True, encoding="utf-8", timeout=120)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            terminal = json.loads(result.stdout)
            self.assertTrue(terminal["ok"])
            observation = json.loads((output / "proof-product-observation.json").read_text(encoding="utf-8"))
            self.assertEqual("proof-slice", observation["source_kind"])
            self.assertFalse(observation["eligible_for_source_selection"])
            self.assertFalse(observation["source_study"]["eligible_for_source_selection"])
            self.assertFalse(observation["coverage"]["complete"])
            self.assertTrue(observation["coverage"]["proof_complete"])
            for profile in ("wide", "narrow"):
                frame = observation["states_by_viewport"][profile]["rest"]["evidence_frames"]["settled"]
                data = (output / frame["file"]).read_bytes()
                self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
                self.assertEqual(frame["sha256"], hashlib.sha256(data).hexdigest())
            titles = {row["profile"]: row for row in observation["proof_component_maps"] if row["selector"] == "#story-title"}
            self.assertEqual("64px", titles["wide"]["properties"]["font-size"])
            self.assertEqual("34px", titles["narrow"]["properties"]["font-size"])
            self.assertEqual(hashlib.sha256(b"A measured product story").hexdigest(), titles["wide"]["text_sha256"])

    def test_proof_media_and_consent_failures_preserve_exact_blockers(self):
        original_url = self.url
        try:
            for suffix, expected in (("broken-visible", "proof-visible-media-decode-failed"), ("broken-hidden", None), ("ambiguous-consent", "consent-handoff-required"),
                                     ("closed-root", "proof-closed-shadow-root-unaddressable"), ("hidden-closed-root", None)):
                with self.subTest(suffix=suffix), tempfile.TemporaryDirectory(prefix="dna proof blockers ") as root:
                    self.url = original_url + suffix
                    output = Path(root)
                    contract = self.make_contract(output, "proof-blocker")
                    result = subprocess.run([NODE, str(SCRIPTS / "observe_reference.mjs"), "--url", self.url, "--id", "proof-blocker", "--out", str(output),
                                             "--state-contract", str(contract), "--proof-source", "--state", "rest"], capture_output=True, text=True, encoding="utf-8", timeout=120)
                    terminal = json.loads(result.stdout)
                    if expected is None:
                        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                        self.assertTrue(terminal["ok"])
                        observation = json.loads((output / "proof-blocker-observation.json").read_text(encoding="utf-8"))
                        self.assertNotIn("#hidden-descendant", [item["selector"] for item in observation["proof_component_maps"]])
                    else:
                        self.assertEqual(expected, terminal["error"]["code"], result.stdout + result.stderr)
                        failure = json.loads((output / "proof-blocker-source-study-failure.json").read_text(encoding="utf-8"))
                        self.assertFalse(failure["eligible_for_source_selection"])
                        self.assertTrue(failure["partial_evidence"]["frames"])
                        if suffix == "broken-visible":
                            self.assertEqual("#product-image", failure["detail"]["media_problems"][0]["selector"])
                            self.assertTrue(failure["detail"]["media_problems"][0]["url"].endswith("/missing.png"))
                        elif suffix == "ambiguous-consent":
                            self.assertEqual("blocked-consent", failure["source_status"])
                        elif suffix == "closed-root":
                            self.assertEqual("#closed-host", failure["detail"]["closed_shadow_roots"][0]["host_selector"])
                            self.assertTrue(failure["detail"]["source_harness_gap"])
        finally:
            self.url = original_url

    def test_recorder_completes_two_real_ninety_second_profiles_and_validated_study_ledgers(self):
        with recording_workspace() as root:
            output = Path(root)
            self.url = self.url + "recording-fixture"
            contract = self.make_contract(output, "recorder-product")
            contract_payload = json.loads(contract.read_text(encoding="utf-8"))
            contract_payload["states"].extend({"id": f"restart-{trigger}", "url": self.url, "kind": "interactive",
                "trigger": {"type": trigger, "target": "#story-restart", "value": None},
                "expectation": f"The restart link exposes its actual source {trigger} treatment."} for trigger in ("hover", "focus"))
            contract.write_text(json.dumps(contract_payload), encoding="utf-8")
            result = subprocess.run([NODE, str(SCRIPTS / "record_reference.mjs"), "--url", self.url, "--id", "recorder-product", "--out", str(output),
                                     "--state-contract", str(contract), "--seconds", "90", "--fps", "15"], capture_output=True, text=True, encoding="utf-8", timeout=480)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["ok"])
            recording = json.loads((output / "recorder-product-recording.json").read_text(encoding="utf-8"))
            spec = importlib.util.spec_from_file_location("source_runtime_validator", SCRIPTS / "init_project_state.py")
            validator = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = validator
            spec.loader.exec_module(validator)
            for profile in ("wide", "narrow"):
                captured = recording["profiles"][profile]
                representative = recording["captures_by_viewport"][profile]
                self.assertEqual({key: captured["source_entry_capture"][key] for key in ("file", "bytes", "sha256")}, representative)
                self.assertNotEqual({key: captured["frames"]["files"][0][key] for key in ("file", "bytes", "sha256")}, representative)
                self.assertEqual(self.url, captured["source_entry_capture"]["source_url"])
                self.assertEqual(captured["navigations"][0], captured["source_entry_capture"]["navigation"])
                self.assertEqual(b"\x89PNG\r\n\x1a\n", (output / representative["file"]).read_bytes()[:8])
                self.assertGreaterEqual(captured["duration_s"], 90)
                self.assertGreaterEqual(captured["frames"]["count"], 1350)
                self.assertTrue(captured["coverage"]["complete"])
                hook_inventory = captured["interaction_census"]["pages"][0]["dom_code_inventory"]["gesture_listeners"]
                self.assertFalse(hook_inventory["observed_gesture_behavior"])
                self.assertTrue(hook_inventory["owners"])
                self.assertTrue(all(owner["disposition"] == "unverified-code-hook-candidate" for owner in hook_inventory["owners"]))
                self.assertEqual([], validator.source_study_evidence_failures(captured["source_study"], artifact_root=output,
                    expected_producer="record_reference.mjs", expected_id="recorder-product-study", expected_profile=profile,
                    required_artifact_kinds={"frame", "video"}))
            ledger_path = output / "recorder-product-artifacts.json"
            failures, _ = validator.reference_recording_failures(recording, recording=output / "recorder-product-recording.json",
                ledger_payload=json.loads(ledger_path.read_text(encoding="utf-8")), ledger=ledger_path,
                state_contract=contract, state_contract_sha256=hashlib.sha256(contract.read_bytes()).hexdigest(), expected_reference_id="recorder-product", signature_kind="static")
            self.assertEqual([], failures, "\n".join(failures))
            blank_substitution = json.loads(json.dumps(recording))
            blank_substitution["captures_by_viewport"]["wide"] = {key: recording["profiles"]["wide"]["frames"]["files"][0][key] for key in ("file", "bytes", "sha256")}
            failures, _ = validator.reference_recording_failures(blank_substitution, recording=output / "recorder-product-recording.json",
                ledger_payload=json.loads(ledger_path.read_text(encoding="utf-8")), ledger=ledger_path,
                state_contract=contract, state_contract_sha256=hashlib.sha256(contract.read_bytes()).hexdigest(), expected_reference_id="recorder-product", signature_kind="static")
            self.assertTrue(any("raw pre-navigation frame" in failure for failure in failures), failures)
            self.assertTrue((output / recording["profiles"]["wide"]["frames"]["files"][0]["file"]).is_file())


if __name__ == "__main__":
    unittest.main()

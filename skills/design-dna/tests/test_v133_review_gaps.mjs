import test from 'node:test';
import assert from 'node:assert/strict';
import {behaviorDriverProblems, gapEvidenceProblems} from '../scripts/check_build.mjs';
import {discoverBrowserExecutable, resolvePlaywright} from '../scripts/playwright_resolver.mjs';
import {hoverProbe} from '../scripts/study_reference.mjs';

test('matching a type cannot substitute for matching its driver and source', () => {
  assert.equal(behaviorDriverProblems(['swap'], [{type:'swap',driver:'time'}], [{type:'swap',driver:'scroll'}]).length, 1);
  assert.equal(behaviorDriverProblems(['swap'], [], [{type:'swap',driver:'time'}]).length, 1);
  assert.deepEqual(behaviorDriverProblems(['swap'], [{type:'swap',driver:'time'}], [{type:'swap',driver:'time'}]), []);
});
test('gap prose and missing artifacts never close an observation gap', () => {
  const gaps=[{code:'horizontal-untraversed',page:'home',viewport:'wide'}];
  assert.equal(gapEvidenceProblems(gaps, 'I checked everything and it is fine', import.meta.filename).length,1);
  assert.equal(gapEvidenceProblems(gaps,[{...gaps[0],method:'scrolled the strip',observed:'last panel visible',artifacts:[{file:'absent.png',sha256:'a'.repeat(64)}]}],import.meta.filename).length,1);
});
test('explicit executables cannot bypass installed Chrome policy', () => {
  const previous=process.env.DESIGN_DNA_ALLOW_BUNDLED_CHROMIUM;
  delete process.env.DESIGN_DNA_ALLOW_BUNDLED_CHROMIUM;
  try {assert.throws(()=>discoverBrowserExecutable({},process.execPath), /installed Google Chrome/);}
  finally {if(previous===undefined) delete process.env.DESIGN_DNA_ALLOW_BUNDLED_CHROMIUM;else process.env.DESIGN_DNA_ALLOW_BUNDLED_CHROMIUM=previous;}
});
test('hover elsewhere on the route does not qualify a quiet section', async () => {
  const pw=resolvePlaywright({moduleUrl:import.meta.url}).playwright;
  const executable=discoverBrowserExecutable(pw);
  assert.equal(executable.name,'chrome');
  const browser=await pw.chromium.launch({executablePath:executable.path});
  try {
    const page=await browser.newPage();
    await page.setContent('<style>button{width:180px;height:70px;background:white} #active:hover{background:red}</style><section id="one"><button id="active">Responds</button></section><section id="two"><button>Quiet</button></section>');
    assert.equal((await hoverProbe(page,'#one')).responded,1);
    assert.equal((await hoverProbe(page,'#two')).responded,0);
  } finally {await browser.close();}
});

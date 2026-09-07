import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {signaturePlanProblems,signatureBuildProblems,gapDispositionProblems,reviewTransferProblems,digest} from '../scripts/signature_contract.mjs';
import {sequencePlanProblems,captureTransferSequence} from '../scripts/signature_sequence.mjs';

const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-signature-test-'));
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
const artifact={file:'region.png',sha256:digest(png)};
function fixture(dynamic=false){
  const studies=new Map();
  const references=Array.from({length:4},(_,i)=>{
    const id='ref-'+i,url=`https://ref${i}.test/`;
    fs.mkdirSync(path.join(root,id),{recursive:true});fs.writeFileSync(path.join(root,id,'region.png'),png);
    // Synthetic header fixture tests evidence identity, not video decoding.
    const video=Buffer.concat([Buffer.from([26,69,223,163]),Buffer.alloc(40)]);
    fs.writeFileSync(path.join(root,id,'sequence.webm'),video);
    const profile={kind:dynamic?'interactive':'static',driver:dynamic?'scroll':'static',medium:'image',composition:'Photo next to editorial statement',pacing:'The composition stays readable',sequence:dynamic?['opening','changed']:['settled'],mechanisms:dynamic?['swap']:[],evidence:[artifact]};
    if(dynamic)profile.evidence.push({file:'sequence.webm',sha256:digest(video)});
    studies.set(id,{pages:['wide','narrow'].map((viewport)=>({url,viewport,ok:true,regions:[{selector:'.source',count:1,media:['image'],keys:['div.source'],selectors:['#source'],evidence:artifact}],motion:{mechanisms:dynamic?[{selector:'#source',tag:'div',cls:'source',type:'swap',driver:'scroll'}]:[]}}))});
    return {id,url,signature_mechanisms:dynamic?['swap']:[],signature_spec:{page:url,selector:'.source',wide:structuredClone(profile),narrow:structuredClone(profile)}};
  });
  const sections=references.map((r,i)=>({selector:'.section-'+i,reference:r.id,signature_from:[r.id],behavior:dynamic?'swap':'none',signature_transfer:Object.fromEntries(['wide','narrow'].map(vp=>[vp,{reference:r.id,medium:'image',driver:dynamic?'scroll':'static',mechanisms:dynamic?['swap']:[],sequence:dynamic?['opening','changed']:['settled']}]))}));
  const source_region={page:references[0].url,selector:'.source'};
  return {studies,plan:{references,routes:[{name:'home',dominant:'ref-0',system_sections:{opening:'.section-0',navigation:'.header',ending:'.footer'},sections:[{selector:'.header',reference:'ref-0',source_region},...sections,{selector:'.footer',reference:'ref-0',source_region}]}]}};
}
test.after(()=>fs.rmSync(root,{recursive:true,force:true}));
test('a substantial static composition can satisfy the contract without animation',()=>{
  const {plan,studies}=fixture();assert.deepEqual(signaturePlanProblems(plan,studies,root),[]);
});
test('a faithfully mapped interactive signature satisfies the plan contract',()=>{
  const {plan,studies}=fixture(true);assert.deepEqual(signaturePlanProblems(plan,studies,root),[]);
});
test('behavior:none cannot erase a chosen interactive source',()=>{
  const {plan,studies}=fixture(true);plan.routes[0].sections[1].behavior='none';
  assert.ok(signaturePlanProblems(plan,studies,root).some(p=>p.includes('behavior:none strips')));
});
test('an unrelated effect cannot replace the chosen sequence or driver',()=>{
  const {plan,studies}=fixture(true);plan.routes[0].sections[1].signature_transfer.wide.mechanisms=['reveal'];plan.routes[0].sections[1].signature_transfer.narrow.driver='time';
  const failures=signaturePlanProblems(plan,studies,root);assert.ok(failures.some(p=>p.includes('swap was omitted')));assert.ok(failures.some(p=>p.includes('incompatible')));
});
test('a matching class in another region cannot supply the source behavior',()=>{
  const {plan,studies}=fixture(true);
  studies.get('ref-0').pages[0].motion.mechanisms[0].selector='#outside';
  assert.ok(signaturePlanProblems(plan,studies,root).some(p=>p.includes('not measured within')));
});
test('relabeling observed dynamic content static fails',()=>{
  const {plan,studies}=fixture(true);plan.references[0].signature_spec.wide.kind='static';plan.references[0].signature_spec.wide.driver='static';plan.references[0].signature_spec.wide.mechanisms=[];
  assert.ok(signaturePlanProblems(plan,studies,root).some(p=>p.includes('cannot be erased')));
});
test('ancillary palette references do not count and cannot own the route',()=>{
  const {plan,studies}=fixture();plan.references[0].role='ancillary';
  const failures=signaturePlanProblems(plan,studies,root);assert.ok(failures.some(p=>p.includes('four substantial')));assert.ok(failures.some(p=>p.includes('dominant must')));
});
test('excluding a signature region fails, excluding an unrelated footer can stand',()=>{
  const {plan}=fixture();const ref=plan.references[0],gap={page:'home',viewport:'wide',code:'overlay-at-rest'};
  ref.gap_reviews=[{...gap,disposition:'excluded',excluded_selectors:['.source'],unrelated_reason:'This is the main source region'}];
  assert.ok(gapDispositionProblems([gap],ref,root).length);
  ref.gap_reviews[0].excluded_selectors=['.irrelevant-footer'];
  assert.deepEqual(gapDispositionProblems([gap],ref,root),[]);
});
test('missing medium cannot pass through a matching palette',()=>{
  const {plan}=fixture();const probes=['wide','narrow'].map(viewport=>({route:'home',viewport,regions:plan.routes[0].sections.map(s=>({selector:s.selector,count:1,media:['typography']}))}));
  assert.ok(signatureBuildProblems(plan,probes).some(p=>p.includes('image signature medium')));
});
test('missing or materially failed visual reviews prevent readiness',()=>{
  const {plan}=fixture();assert.ok(reviewTransferProblems(plan,'',root).length);
  plan.review={transfers:[],issues:[{severity:'material',status:'open',message:'Defining image sequence absent'}]};
  assert.ok(reviewTransferProblems(plan,'',root).some(p=>p.includes('material visual issue')));
});
test('a completed paired review can pass and cannot hide an open material issue',()=>{
  const {plan}=fixture();
  fs.writeFileSync(path.join(root,'build.png'),png);
  plan.review={issues:[],transfers:plan.routes[0].sections.flatMap(section=>['wide','narrow'].map(viewport=>({route:'home',selector:section.selector,reference:section.reference,viewport,status:'present',composition:'Compared source and build arrangement',crop:'Compared the image framing',hierarchy:'Compared the type hierarchy',pacing:'Compared the readable pacing',sequence:'Compared ordered state captures',interaction:'Compared expected user response',image_accuracy:'Reviewed product image and label',evidence:[{...artifact,file:section.reference+'/region.png',side:'source'},{...artifact,file:'build.png',side:'build'}]})))};
  assert.deepEqual(reviewTransferProblems(plan,'',root),[]);
  plan.review.issues.push({severity:'material',status:'open',message:'Missing defining scene'});
  assert.ok(reviewTransferProblems(plan,'',root).some(p=>p.includes('Missing defining scene')));
});
test('a source name alone does not authorize navigation or an invented page shell',()=>{
  const {plan,studies}=fixture();delete plan.routes[0].sections[0].source_region;
  assert.ok(signaturePlanProblems(plan,studies,root).some(p=>p.includes('naming a reference alone')));
});
test('the same artifact cannot serve as both sides of a comparison',()=>{
  const {plan}=fixture();plan.review={issues:[],transfers:[{route:'home',selector:'.header',reference:'ref-0',viewport:'wide',status:'present',evidence:[{...artifact,file:'ref-0/region.png',side:'source'},{...artifact,file:'ref-0/region.png',side:'build'}]}]};
  assert.ok(reviewTransferProblems(plan,'',root).some(p=>p.includes('cannot also be labeled')));
});
test('a wrong input driver or omitted state fails sequence validation',()=>{
  assert.ok(sequencePlanProblems({driver:'scroll',sequence:['opening','end'],steps:[{action:'rest',expect:{selector:':scope',visibility:'visible'}},{action:'time',ms:100,expect:{selector:'.end',visibility:'visible'}}]}).length);
});
test('targeted sequence records the changed state and refuses a missing result',async()=>{
  let shifted=false;
  const target={count:async()=>1,isVisible:async()=>shifted,innerText:async()=>shifted?'Second state':'First state'};
  const region={count:async()=>1,evaluate:async()=>{},boundingBox:async()=>null,locator:()=>target,isVisible:async()=>true};
  const page={locator:()=>region,mouse:{wheel:async()=>{shifted=true;}},waitForTimeout:async()=>{},evaluate:async()=>[{selector:'.stage',count:1,media:['image'],state:shifted?'second':'first'}],screenshot:async()=>png};
  const section={selector:'.stage',signature_transfer:{wide:{reference:'ref-0',driver:'scroll',sequence:['first','second'],steps:[{action:'rest',expect:{selector:':scope',visibility:'visible'}},{action:'scroll',delta:300,expect:{selector:'.second',visibility:'visible',text:'Second state'}}]}}};
  const good=await captureTransferSequence(page,section,'wide',root,'good');assert.equal(good.states.length,2);assert.deepEqual(good.problems,[]);
  shifted=false;page.mouse.wheel=async()=>{};
  const bad=await captureTransferSequence(page,section,'wide',root,'bad');assert.ok(bad.problems.length);assert.equal(bad.states.length,1);
});

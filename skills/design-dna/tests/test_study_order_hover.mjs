import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {studyPage,HOVER_SNAPSHOT} from '../scripts/study_reference.mjs';

test('supporting-region traversal cannot consume the first-visit motion observation',async()=>{
  for(const selectors of [[],['.story','.footer']]){
    let consumed=false;
    const events=[];
    const page={goto:async()=>({status:()=>200}),url:()=> 'https://source.test/',screenshot:async()=>Buffer.from('fixture'),video:()=>null,close:async()=>{},
      evaluate:async(fn)=>typeof fn==='function'?[{count:1,selectors:['#future']}]:{},
      locator:()=>({count:async()=>1,evaluate:async()=>{consumed=true;events.push('region');}})};
    const context={newPage:async()=>page,close:async()=>{}};
    const browser={newContext:async()=>context};
    const env={browser,options:{frameDir:'frames',videoDir:'videos',prefix:'wide',videoSeconds:25,full:true,regions:selectors},viewport:{name:'wide'},
      bounded:async p=>p,sleep:async()=>{},sha:()=> 'fixture-sha',fs:{writeFileSync:()=>{}},path:{join:(...p)=>p.join('/')},
      DESIGN_SYSTEM:'design',LAYOUT:'layout',handleOverlays:async()=>({dismissed:false}),hoverProbe:async()=>({}),restPass:async()=>({}),
      motionPass:async()=>{events.push('motion');const mechanisms=consumed?[]:[{type:'reveal',driver:'scroll'}];consumed=true;return {mechanisms};},
      animationsByDepth:async()=>[],annotateDrivers:m=>m,groundSample:async()=>({}),scrollThrough:async()=>{events.push('recording');return [];},
      inspectRegions:function inspect(){},observationGaps:()=>[]};
    const result=await vm.runInNewContext(`(${studyPage.toString()})(browser,'https://source.test/',viewport,options)`,env);
    assert.equal(result.ok,true);assert.equal(result.motion.mechanisms.length,1);
    assert.equal(result.regions.length,selectors.length);
    assert.deepEqual(events,['motion','recording',...selectors.map(()=> 'region')]);
  }
});

test('hover snapshot sees pseudo underline and border feedback without inventing quiet responses',()=>{
  let hovered=false,mode='pseudo';
  const el={querySelectorAll:()=>[],getBoundingClientRect:()=>({left:10,top:10,width:80,height:30})};
  const getComputedStyle=(n,pseudo)=>{
    if(pseudo)return {content:pseudo==='::after'?'""':'none',transform:mode==='pseudo'&&hovered?'scaleX(1)':'scaleX(0)',height:'1px',width:'80px',opacity:'1'};
    return {color:'black',borderBottomColor:mode==='border'&&hovered?'red':'black',borderBottomWidth:'1px',borderBottomStyle:'solid'};
  };
  const snapshot=()=>vm.runInNewContext(`${HOVER_SNAPSHOT}('one')`,{document:{querySelector:()=>el},getComputedStyle}).rows[0];
  for(mode of ['pseudo','border','quiet']){hovered=false;const before=snapshot();hovered=true;const after=snapshot();assert.equal(before!==after,mode!=='quiet');}
});

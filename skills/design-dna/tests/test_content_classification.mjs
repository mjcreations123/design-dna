import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {repeatedImages,iconCardRow,contentRoles} from '../scripts/content_classification.mjs';
import {inspectRegions} from '../scripts/signature_contract.mjs';
import {FUNCTIONAL} from '../scripts/check_build.mjs';

const box={width:800,height:800,left:0,right:800,top:100,bottom:900,x:0,y:100};
const style={display:'block',visibility:'visible',opacity:'1',position:'static',top:'100px',backgroundImage:'none'};
const run=(fn,args,env)=>vm.runInNewContext(`(${fn.toString()})(${JSON.stringify(args)})`,env);
test('functional probe remains callable with serialized planned sections',()=>{
  const result=vm.runInNewContext(`${FUNCTIONAL}([])`,{innerWidth:1440,innerHeight:900,document:{querySelectorAll:()=>[],activeElement:null,body:{innerText:'A readable content page with sufficient text for this smoke fixture.'}}});
  assert.equal(result.blank,false);assert.equal(result.content_roles.sticky_content,0);
});
const image=(where,src='https://example.test/seal.webp',size=72)=>({currentSrc:src,alt:'Agency seal',getBoundingClientRect:()=>({...box,width:size,height:size}),closest:s=>s==='a[href]'?{href:'https://example.test/',className:'identity',getAttribute:()=>null}:s.startsWith(where)?{}:null});
test('header/footer seal is retained as identity evidence, body repetition still fails',()=>{
  let imgs=[image('header'),image('footer')];
  const env={URL,location:{href:'https://example.test/about',origin:'https://example.test'},document:{querySelectorAll:()=>imgs}};
  let r=run(repeatedImages,null,env);
  assert.equal(r.duplicate_images.length,0);assert.equal(r.repeated_identity_marks.length,1);
  imgs.push(image('main'));r=run(repeatedImages,null,env);assert.equal(r.duplicate_images.length,1);
  imgs=[image('header',undefined,400),image('footer',undefined,400)];assert.equal(run(repeatedImages,null,env).duplicate_images.length,1);
});
test('long distinct image URLs do not collide by prefix and length',()=>{
  const prefix='https://example.test/'+ 'x'.repeat(250);
  const imgs=[image('main',prefix+'a'),image('main',prefix+'b')];
  assert.equal(run(repeatedImages,null,{URL,location:{href:'https://example.test/',origin:'https://example.test'},document:{querySelectorAll:()=>imgs}}).duplicate_images.length,0);
});
test('three office addresses are not icon cards; icons must be observed',()=>{
  const row={display:'grid',grid:'300px 300px 300px',text_chars:200,top:800,item_count:3};
  assert.equal(iconCardRow(row),false);assert.equal(iconCardRow({...row,icon_items:0}),false);
  assert.equal(iconCardRow({...row,icon_items:3}),true);
  assert.equal(iconCardRow({...row,icon_items:3,item_count:5}),false);
});

function roleFixture(){
  const main={};
  const root={parentElement:null,children:[],getBoundingClientRect:()=>({...box,height:2600,bottom:2700}),closest:s=>s==='main'?main:null,querySelectorAll:()=>[stage,...stage.children],getAttribute:()=>null};
  const stage={parentElement:root,children:[],getBoundingClientRect:()=>box,closest:s=>s==='main'?main:null,querySelectorAll:()=>[],getAttribute:()=>null};
  const panel=(hidden)=>({tagName:'ARTICLE',parentElement:stage,tabIndex:-1,children:[],getBoundingClientRect:()=>box,closest:()=>null,querySelectorAll:()=>[],getAttribute:n=>n==='aria-hidden'?(hidden?'true':'false'):null,hidden});
  const active=panel(false),inactive=panel(true);stage.children=[active,inactive];root.children=[stage];
  const env={innerHeight:900,document:{querySelectorAll:()=>[root]},getComputedStyle:el=>({...style,position:el===stage?'sticky':'static',opacity:el.hidden?'0':'1'})};
  return {root,stage,active,inactive,env};
}
const section=[{selector:'.story',states:3,behavior:'pinned; reveal'}];
test('800px planned in-flow story below 100px header is content, not a fixed overlay',()=>{
  const f=roleFixture();assert.equal(run(contentRoles,section,f.env).stickyContent.length,1);
  const original=f.env.getComputedStyle;f.env.getComputedStyle=el=>({...original(el),position:el===f.stage?'fixed':'static'});
  assert.equal(run(contentRoles,section,f.env).stickyContent.length,0);
});
test('dialog, unplanned and unreserved sticky layers stay overlay candidates',()=>{
  let f=roleFixture();assert.equal(run(contentRoles,[],f.env).stickyContent.length,0);
  f.stage.closest=()=>({});assert.equal(run(contentRoles,section,f.env).stickyContent.length,0);
  f=roleFixture();f.root.getBoundingClientRect=()=>box;assert.equal(run(contentRoles,section,f.env).stickyContent.length,0);
});
test('inactive nonfocusable panel with an active sibling is distinguished; blank and hidden controls are not excused',()=>{
  const f=roleFixture();assert.equal(run(contentRoles,section,f.env).inactivePanels.length,1);
  f.inactive.tabIndex=0;assert.equal(run(contentRoles,section,f.env).inactivePanels.length,0);
  f.inactive.tabIndex=-1;f.active.hidden=true;assert.equal(run(contentRoles,section,f.env).inactivePanels.length,0);
});
test('region membership includes hidden descendants but does not count their painted media',()=>{
  const node=(tag,id,hidden=false)=>({tagName:tag,id,nodeType:1,parentElement:null,previousElementSibling:null,childNodes:[],children:[],innerText:'',hidden,getBoundingClientRect:()=>box,getAttribute:()=>'',querySelectorAll:()=>[]});
  const root=node('SECTION','story'),future=node('IMG','future',true);future.parentElement=root;root.children=[future];root.querySelectorAll=()=>[future];
  const r=run(inspectRegions,['#story'],{document:{querySelectorAll:s=>s==='#future'?[future]:[root]},CSS:{escape:s=>s},getComputedStyle:el=>({...style,opacity:el.hidden?'0':'1'}),innerWidth:1440,innerHeight:900})[0];
  assert.ok(r.selectors.includes('#future'));assert.ok(!r.media.includes('image'));assert.equal(r.images.length,0);assert.equal(r.state.length,1);
});

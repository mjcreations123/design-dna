import test from 'node:test';
import assert from 'node:assert/strict';
import {ownerSelectionProblems} from '../scripts/owner_selection.mjs';

const fixture=()=>({owner_selection:{candidates:Array.from({length:10},(_,i)=>({id:`s${i}`,url:`https://site${i}.test/`,fit:'Overall hierarchy suits the project audience and content'})),user_instructions:'Use the whole design of site zero for this page.',choices:[{id:'whole-page',reference:'s0',parts:'Whole page, navigation and ending'}]},references:[{id:'s0'}],routes:[{name:'home',sections:[{selector:'.page',reference:'s0',owner_choices:['whole-page']}]}]});
test('ten candidates do not force ten or four sources into the user-selected build',()=>assert.deepEqual(ownerSelectionProblems(fixture()),[]));
test('no user choice blocks implementation even after candidate research',()=>{
  const p=fixture();p.owner_selection.choices=[];p.owner_selection.user_instructions='';
  assert.ok(ownerSelectionProblems(p).some(x=>x.includes('no user-selected parts')));
  assert.ok(ownerSelectionProblems({}).some(x=>x.includes('wait for the user')));
});
test('fewer than ten or duplicate websites do not satisfy the first presentation',()=>{
  const p=fixture();p.owner_selection.candidates.pop();assert.ok(ownerSelectionProblems(p).length);
  const q=fixture();q.owner_selection.candidates[9].url=q.owner_selection.candidates[0].url;assert.ok(ownerSelectionProblems(q).length);
});
test('unselected source or uncovered footer is rejected',()=>{
  const p=fixture();p.references.push({id:'s1'});p.routes[0].sections.push({selector:'footer',reference:'s1',owner_choices:['whole-page']});
  assert.ok(ownerSelectionProblems(p).some(x=>x.includes('source was not selected')));
  assert.ok(ownerSelectionProblems(p).some(x=>x.includes('no bound user choice')));
});
test('requested additions and explicitly chosen separate footer can be recorded',()=>{
  const p=fixture();p.owner_selection.candidates.push({id:'extra',url:'https://extra.test',fit:'Additional user-requested alternative'});
  p.owner_selection.choices.push({id:'footer-choice',reference:'extra',parts:'Footer only'});p.references.push({id:'extra'});
  p.routes[0].sections.push({selector:'footer',reference:'extra',owner_choices:['footer-choice']});assert.deepEqual(ownerSelectionProblems(p),[]);
});

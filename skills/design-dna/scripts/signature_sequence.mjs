/** Targeted build-state checks within the existing check command. */
import fs from 'node:fs';
import path from 'node:path';
import {digest, inspectRegions} from './signature_contract.mjs';
import {interactionTargetSafety} from './browser_evidence.mjs';

export function sequencePlanProblems(transfer) {
  const steps=transfer?.steps;
  if(!Array.isArray(steps)||!steps.length||steps.length>24)return ['signature transfer needs 1-24 bounded steps'];
  const problems=[];
  if(steps.length!==transfer.sequence?.length)problems.push('one step is required for each declared sequence state');
  for(const [i,step] of steps.entries()){
    if(!step||!['rest','scroll','time','hover','pointer','click'].includes(step.action)) {problems.push(`state ${i}: unknown action`);continue;}
    if(i===0&&step.action!=='rest')problems.push('the sequence must begin with a rest state');
    if(i>0&&step.action!==transfer.driver)problems.push(`state ${i}: action must preserve ${transfer.driver} driver`);
    if(!step.expect?.selector||!['visible','hidden'].includes(step.expect.visibility))problems.push(`state ${i}: expected selector and visible/hidden outcome are required`);
    if(['hover','pointer','click'].includes(step.action)&&!step.target)problems.push(`state ${i}: exact target selector is required`);
    if(step.action==='scroll'&&(!Number.isFinite(step.delta)||Math.abs(step.delta)>10000))problems.push(`state ${i}: wheel delta must be bounded`);
    if(step.action==='time'&&(!Number.isInteger(step.ms)||step.ms<1||step.ms>15000))problems.push(`state ${i}: time dwell must be 1-15000 ms`);
  }
  if(transfer.driver!=='static'&&steps.length<2)problems.push('dynamic transfer needs at least two observed states');
  return problems;
}

export async function captureTransferSequence(page, section, viewport, frameDir, prefix) {
  const transfer=section.signature_transfer?.[viewport];
  if(!transfer)return null;
  const problems=sequencePlanProblems(transfer),states=[];
  if(problems.length)return {selector:section.selector,viewport,problems,states};
  const region=page.locator(section.selector);
  if(await region.count()!==1)return {selector:section.selector,viewport,problems:['signature region is not unique'],states};
  await region.evaluate((el)=>el.scrollIntoView({block:'start',behavior:'instant'}));
  const box=await region.boundingBox({timeout:3000});
  if(box){const vp=page.viewportSize();await page.mouse.move(Math.max(1,Math.min(vp.width-1,box.x+box.width/2)),Math.max(1,Math.min(vp.height-1,box.y+box.height/2)));}
  for(const [index,step] of transfer.steps.entries()){
    try {
      if(step.action==='scroll')await page.mouse.wheel(step.axis==='x'?step.delta:0,step.axis==='x'?0:step.delta);
      if(step.action==='time')await page.waitForTimeout(step.ms);
      if(['hover','pointer','click'].includes(step.action)){
        const target=region.locator(step.target);
        if(await target.count()!==1)throw new Error('input target is not unique inside the signature region');
        if(step.action==='click'){
          const safety=await interactionTargetSafety(target,'click',null);
          if(!safety.safe)throw new Error('click needs a safe disclosure target; review side-effecting flows separately');
          await target.click({timeout:5000});
        }else await target.hover({timeout:5000});
      }
      await page.waitForTimeout(250);
      const expected=step.expect.selector===':scope'?region:region.locator(step.expect.selector);
      const count=await expected.count();
      const visible=count===1&&await expected.isVisible();
      if(step.expect.visibility==='visible'&&!visible||step.expect.visibility==='hidden'&&visible)throw new Error(`expected ${step.expect.selector} ${step.expect.visibility}`);
      if(step.expect.text!==undefined&&(!visible||!(await expected.innerText()).includes(step.expect.text)))throw new Error('expected state text missing');
      const [measurement]=await page.evaluate(inspectRegions,[section.selector]);
      const bytes=await page.screenshot({timeout:10000});
      const file=`${prefix}-signature-${index+1}.png`;
      fs.writeFileSync(path.join(frameDir,file),bytes);
      states.push({name:transfer.sequence[index],action:step.action,expect:step.expect,measurement,evidence:{file:`frames/${file}`,sha256:digest(bytes)}});
    }catch(error){problems.push(`state ${index+1}: ${error.message}`);break;}
  }
  if(transfer.driver!=='static'&&states.length>1&&!transfer.mechanisms?.every((m)=>m==='pinned')&&new Set(states.map((s)=>JSON.stringify(s.measurement.state))).size===1)problems.push('target region did not change through the promised sequence');
  return {selector:section.selector,reference:transfer.reference,viewport,states,problems};
}

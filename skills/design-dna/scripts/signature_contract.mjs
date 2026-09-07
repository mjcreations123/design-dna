/** Small shared checks for the existing plan and review; no process manager. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';

const profiles = ['wide', 'narrow'];
const list = (value) => Array.isArray(value) ? value : [];
const text = (value) => typeof value === 'string' && value.trim().length > 0;
const modes = new Set(['static', 'scroll', 'time', 'hover', 'pointer', 'click']);
export const digest = (value) => createHash('sha256').update(value).digest('hex');
export function artifactProblems(artifacts, base) {
  if (!list(artifacts).length) return ['no captured evidence'];
  const root = path.resolve(base);
  return artifacts.flatMap((item) => {
    try {
      if (!text(item?.file) || !/^[a-f0-9]{64}$/i.test(item.sha256 || '')) throw new Error();
      const file = path.resolve(root, item.file);
      const stat = fs.lstatSync(file);
      if (!stat.isFile() || stat.isSymbolicLink() || stat.size < 32) throw new Error();
      const bytes = fs.readFileSync(file);
      const media = bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])) || bytes.subarray(0,3).equals(Buffer.from([255,216,255])) || bytes.subarray(0,4).equals(Buffer.from([26,69,223,163])) || bytes.subarray(4,8).toString() === 'ftyp';
      if (!media || digest(bytes) !== item.sha256) throw new Error();
      return [];
    } catch { return [`missing, changed or non-media capture: ${item?.file || '(unnamed)'}`]; }
  });
}

export function signaturePlanProblems(plan, studies, studyRoot) {
  const problems = [];
  const refs = list(plan.references), routes = list(plan.routes);
  const substantial = refs.filter((ref) => ref.role !== 'ancillary');
  if (new Set(substantial.map((r) => r.id)).size < 4) problems.push('selection: four substantial references are required; ancillary palette/type citations do not count');
  for (const route of routes) {
    const dominant = refs.find((ref) => ref.id === route.dominant);
    if (!dominant || dominant.role === 'ancillary') problems.push(`${route.name}: dominant must be a substantial selected reference`);
    const system = route.system_sections;
    for (const role of ['opening','navigation','ending']) {
      const selector = system?.[role];
      const section = list(route.sections).find((s) => s.selector === selector);
      if (!section || section.reference !== route.dominant) problems.push(`${route.name}: ${role} must name a planned section owned by its dominant reference (system_sections)`);
    }
  }
  for (const ref of refs) {
    if (ref.role && !['contributor','ancillary'].includes(ref.role)) problems.push(`${ref.id}: role must be contributor or ancillary`);
    if (ref.role === 'ancillary') {
      if (routes.some((r) => list(r.sections).some((s) => s.reference === ref.id || s.behavior_from === ref.id))) problems.push(`${ref.id}: ancillary citations cannot own composition or behavior`);
      continue;
    }
    const spec = ref.signature_spec;
    const mapped = routes.flatMap((route) => list(route.sections).filter((s) => list(s.signature_from).includes(ref.id)).map((section) => ({route,section})));
    if (!mapped.length) problems.push(`${ref.id}: its selected signature reaches no build section; a composition label alone is not a transfer`);
    if (!spec || !text(spec.page) || !text(spec.selector) || ['html','body','main','*'].includes(spec.selector.trim())) {
      problems.push(`${ref.id}: define signature_spec with the exact source page and region selector`);
    }
    for (const viewport of profiles) {
      const profile = spec?.[viewport];
      const label = `${ref.id} ${viewport}`;
      if (!profile || !['static','interactive'].includes(profile.kind) || !modes.has(profile.driver) || !text(profile.composition) || !text(profile.medium) || !text(profile.pacing) || !list(profile.sequence).length || profile.sequence.some((s) => !text(s))) {
        problems.push(`${label}: signature needs kind, driver, medium, composition, pacing, sequence and captured evidence`);
        continue;
      }
      const page = list(studies.get(ref.id)?.pages).find((p) => p.url === spec.page && p.viewport === viewport && p.ok);
      if (!page) problems.push(`${label}: signature source page was not successfully studied`);
      const region = list(page?.regions).find((r) => r.selector === spec.selector && r.count === 1);
      if (!region) problems.push(`${label}: source region is unmeasured; re-study with --region ${spec.selector}`);
      else if (!list(region.media).includes(profile.medium) && !(profile.medium === 'typography' && region.words > 0)) problems.push(`${label}: medium ${profile.medium} is absent from its measured source region`);
      problems.push(...artifactProblems(profile.evidence, path.join(studyRoot, ref.id)).map((p) => `${label}: ${p}`));
      if (region && !list(profile.evidence).some((a) => a.file === region.evidence?.file && a.sha256 === region.evidence?.sha256)) problems.push(`${label}: signature evidence must include the tool's captured source region`);
      if (profile.kind === 'static' && (profile.driver !== 'static' || list(profile.mechanisms).length)) problems.push(`${label}: static signature cannot declare dynamic drivers or mechanisms`);
      if (profile.kind === 'interactive' && (profile.driver === 'static' || profile.sequence.length < 2 || !list(profile.mechanisms).length)) problems.push(`${label}: interactive signature needs a driver, mechanism and at least two ordered states`);
      if (profile.kind === 'interactive' && !list(profile.evidence).some((a)=>/\.(webm|mp4|mov)$/i.test(a.file||'')) && new Set(list(profile.evidence).map((a)=>a.sha256)).size < profile.sequence.length) problems.push(`${label}: capture the source sequence as video or distinct state frames; one still cannot prove it`);
      const promised = list(profile.mechanisms);
      const measured = list(page?.motion?.mechanisms).filter((m) => m.selector && list(region?.selectors).includes(m.selector));
      if (profile.kind === 'static' && (measured.length || ['video','canvas'].includes(profile.medium))) problems.push(`${label}: selected region has measured dynamic content; its defining behavior cannot be erased with a static label`);
      for (const type of promised) {
        if (!['hover','click'].includes(profile.driver) && !measured.some((m) => m.type === type && m.driver === profile.driver)) problems.push(`${label}: ${type}/${profile.driver} was not measured within the named source region`);
      }
      for (const {route,section} of mapped) {
        const transfer = section.signature_transfer?.[viewport];
        if (!transfer || transfer.reference !== ref.id || transfer.medium !== profile.medium || transfer.driver !== profile.driver || !list(transfer.sequence).length || transfer.sequence.length !== profile.sequence.length) problems.push(`${route.name} ${section.selector} ${viewport}: missing or incompatible signature transfer for ${ref.id}`);
        const behavior = String(viewport === 'narrow' ? section.behavior_narrow ?? section.behavior : section.behavior);
        if (profile.kind === 'interactive' && /^(none|no)\b/i.test(behavior.trim())) problems.push(`${route.name} ${section.selector} ${viewport}: behavior:none strips ${ref.id}'s selected signature`);
        for (const type of promised) if (!list(transfer?.mechanisms).includes(type)) problems.push(`${route.name} ${section.selector} ${viewport}: selected signature mechanism ${type} was omitted`);
      }
    }
    // Existing declarations are binding too; a new static spec cannot erase them.
    for (const type of list(ref.signature_mechanisms)) if (!profiles.some((vp) => list(spec?.[vp]?.mechanisms).includes(type))) problems.push(`${ref.id}: previously declared signature mechanism ${type} has no transfer obligation`);
  }
  for (const route of routes) for (const section of list(route.sections)) for (const id of list(section.signature_from)) {
    if (!substantial.some((r) => r.id === id)) problems.push(`${route.name} ${section.selector}: unknown or ancillary signature ${id}`);
  }
  return problems;
}

export function gapDispositionProblems(gaps, ref, studiesRoot) {
  const problems = [];
  for (const gap of gaps) {
    const review = list(ref.gap_reviews).find((r) => r?.code === gap.code && r.page === gap.page && (r.viewport || '') === (gap.viewport || ''));
    const label = `${ref.id} ${gap.code} ${gap.viewport || ''}`;
    if (!review || !['inspected','excluded'].includes(review.disposition)) {problems.push(`${label}: say inspected or excluded; exclusion does not resolve a gap`);continue;}
    if (review.disposition === 'excluded') {
      const sourcePage = ref.signature_spec?.page;
      const samePage = gap.page === sourcePage || gap.page === 'home' && sourcePage === ref.url;
      const excluded = list(review.excluded_selectors);
      if (!excluded.length || excluded.some((s) => !text(s))) problems.push(`${label}: excluded regions need exact selectors`);
      if (ref.role !== 'ancillary' && samePage && (!text(review.unrelated_reason) || excluded.some((s) => ['html','body','main','*',ref.signature_spec?.selector].includes(s)))) problems.push(`${label}: exclusion removes or leaves the selected signature unverified; re-study or replace this contributor`);
    } else {
      // Reusing an old obstructed first screen cannot demonstrate new inspection.
      const root = path.resolve(studiesRoot, ref.id);
      const studyFile = path.join(root,'study.json');
      let prior = new Set();
      try {
        const study = JSON.parse(fs.readFileSync(studyFile,'utf8'));
        prior = new Set(list(study.pages).flatMap((p) => [p.first_screen?.sha256,p.first_screen_clear?.sha256,...list(p.frames).map((f) => f.sha256)]).filter(Boolean));
      } catch { /* existence is checked by the caller */ }
      if (!list(review.artifacts).some((a) => a?.sha256 && !prior.has(a.sha256))) problems.push(`${label}: inspected requires new state evidence, not the existing study screenshot`);
    }
  }
  return problems;
}

/** Runs read-only in either the source or build page. */
export function inspectRegions(selectors) {
  const selectorFor = (el) => {if(el.id && document.querySelectorAll('#'+CSS.escape(el.id)).length===1)return '#'+CSS.escape(el.id);const parts=[];for(let n=el;n&&n.nodeType===1;n=n.parentElement){let index=1;for(let p=n.previousElementSibling;p;p=p.previousElementSibling)index++;parts.unshift(n.tagName.toLowerCase()+':nth-child('+index+')');}return parts.join(' > ');};
  const visible = (el) => {const r=el.getBoundingClientRect();if(r.width<=0||r.height<=0)return false;for(let n=el;n;n=n.parentElement){const s=getComputedStyle(n);if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity)===0)return false;}return true;};
  const key = (el) => el.tagName.toLowerCase()+'.'+String(el.getAttribute('class')||'').split(/\s+/)[0];
  return selectors.map((selector) => {
    let nodes;try{nodes=document.querySelectorAll(selector);}catch{return {selector,count:-1};}
    if(nodes.length!==1)return {selector,count:nodes.length};
    const root=nodes[0],all=[root,...root.querySelectorAll('*')].filter(visible),box=root.getBoundingClientRect();
    const media=new Set();
    for(const el of all){if(el.tagName==='IMG')media.add('image');if(el.tagName==='VIDEO')media.add('video');if(el.tagName==='CANVAS')media.add('canvas');if(el.tagName==='SVG')media.add('svg');if(getComputedStyle(el).backgroundImage!=='none')media.add('background');}
    const words=(root.innerText||'').trim().split(/\s+/).filter(Boolean).length;
    if(words)media.add('typography');
    return {selector,count:1,keys:all.map(key),selectors:all.map(selectorFor),media:[...media],words,width:box.width,height:box.height,viewport:{width:innerWidth,height:innerHeight},
      state:all.map((el)=>{const s=getComputedStyle(el),r=el.getBoundingClientRect();return [key(el),(el.childNodes.length&&[...el.childNodes].filter((n)=>n.nodeType===3).map((n)=>n.textContent).join(''))||'',el.currentSrc||'',el.tagName==='VIDEO'?el.currentTime:null,s.transform,s.opacity,s.color,s.backgroundColor,Math.round(r.x-box.x),Math.round(r.y-box.y)];}),
      images:all.filter((el)=>el.tagName==='IMG').map((el)=>({src:el.currentSrc,alt:el.alt,loaded:el.complete&&el.naturalWidth>0})),
      children:[...root.children].filter(visible).map((el)=>{const r=el.getBoundingClientRect();return {tag:el.tagName.toLowerCase(),x:(r.x-box.x)/Math.max(1,box.width),y:(r.y-box.y)/Math.max(1,box.height),width:r.width/Math.max(1,box.width),height:r.height/Math.max(1,box.height)};})};
  });
}

export function signatureBuildProblems(plan, probes) {
  const problems=[];
  for(const route of list(plan.routes))for(const section of list(route.sections))for(const viewport of profiles){
    const transfer=section.signature_transfer?.[viewport];if(!transfer)continue;
    const region=probes.find((p)=>p.route===(route.name||route.url)&&p.viewport===viewport)?.regions?.find((r)=>r.selector===section.selector);
    if(!region||region.count!==1)problems.push(`${route.name} ${section.selector} ${viewport}: signature requires one exact rendered region`);
    else if(!region.media.includes(transfer.medium))problems.push(`${route.name} ${section.selector} ${viewport}: ${transfer.medium} signature medium was replaced or removed`);
  }
  return problems;
}

export function reviewTransferProblems(plan, reviewText, base) {
  const problems=[];
  if(!Array.isArray(plan.review?.issues))problems.push('review.issues must explicitly classify unresolved findings, or be an empty array');
  const rows=list(plan.review?.transfers);
  for(const route of list(plan.routes))for(const section of list(route.sections))for(const id of list(section.signature_from))for(const viewport of profiles){
    const row=rows.find((r)=>r.route===(route.name||route.url)&&r.selector===section.selector&&r.reference===id&&r.viewport===viewport);
    const label=`${route.name} ${section.selector} ${viewport}`;
    if(!row||row.status!=='present') {problems.push(`${label}: signature review is ${row?.status||'missing'}`);continue;}
    for(const field of ['composition','crop','hierarchy','pacing','sequence','interaction','image_accuracy']) if(!text(row[field])) problems.push(`${label}: review must address ${field}`);
    problems.push(...artifactProblems(row.evidence,base).map((p)=>`${label}: ${p}`));
    if(!list(row.evidence).some((a)=>a.side==='source')||!list(row.evidence).some((a)=>a.side==='build'))problems.push(`${label}: review must bind both source and build captures`);
  }
  for(const issue of list(plan.review?.issues)){
    if(!issue||!['material','minor'].includes(issue.severity)||!['open','resolved'].includes(issue.status)||!text(issue.message))problems.push('review issue needs severity, status and message');
    else if(issue.severity==='material'&&issue.status!=='resolved')problems.push(`material visual issue remains: ${issue.message}`);
  }
  return problems;
}

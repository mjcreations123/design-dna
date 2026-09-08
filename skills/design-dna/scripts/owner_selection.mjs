// A small record in the existing plan, not an approval service or shared state.
// Checks record completeness and consistency, not whether a user truly said it.
export function ownerSelectionProblems(plan) {
  const problems=[],selection=plan.owner_selection;
  const text=v=>typeof v==='string'&&v.trim().length>0;
  const list=v=>Array.isArray(v)?v:[];
  if(!selection)return ['owner_selection is missing: present ten candidates and wait for the user to choose parts before building'];
  const candidates=list(selection.candidates),ids=new Set(),sites=new Set();
  for(const c of candidates){
    let site;try{const u=new URL(c.url);if(!/^https?:$/.test(u.protocol))throw new Error();site=u.hostname.toLowerCase().replace(/^www\./,'');}catch{}
    if(!text(c.id)||ids.has(c.id)||!site||sites.has(site)||!text(c.fit))problems.push('owner_selection candidates need distinct website IDs/hosts, working HTTP(S) URLs and overall project-fit reasons');
    ids.add(c.id);if(site)sites.add(site);
  }
  if(candidates.length<10||sites.size<10)problems.push('owner_selection must retain the initial ten distinct website candidates; requested additions may follow');
  if(!text(selection.user_instructions))problems.push('owner_selection.user_instructions must preserve the actual user selection, not producer approval');
  const choices=list(selection.choices),byId=new Map();
  for(const c of choices){
    if(!text(c.id)||byId.has(c.id)||!ids.has(c.reference)||!text(c.parts))problems.push('owner choices need unique IDs, presented reference IDs and the parts the user selected');
    byId.set(c.id,c);
  }
  if(!choices.length)problems.push('no user-selected parts: stop after candidate presentation');
  const refs=list(plan.references);
  for(const ref of refs)if(!choices.some(c=>c.reference===ref.id))problems.push(`${ref.id}: source was not selected by the user`);
  for(const route of list(plan.routes))for(const section of list(route.sections)){
    const bound=list(section.owner_choices).map(id=>byId.get(id));
    if(!bound.length||bound.some(c=>!c))problems.push(`${route.name} ${section.selector}: bind owner_choices to the user's selected parts`);
    for(const ref of new Set([section.reference,section.palette_from,section.behavior_from,...list(section.signature_from)].filter(Boolean)))
      if(!bound.some(c=>c?.reference===ref))problems.push(`${route.name} ${section.selector}: ${ref} has no bound user choice for this section`);
  }
  return problems;
}

/** Read-only DOM probe; serialized into the checker, with no external dependencies. */
export function repeatedImages() {
  const seen=new Map();
  for(const img of document.querySelectorAll('img')) {
    const src=img.currentSrc||img.src||'',r=img.getBoundingClientRect();
    if(!src||r.width<40||r.height<40)continue;
    const link=img.closest('a[href]');
    let home=false;
    try {const u=new URL(link?.href||'',location.href);home=!!link&&u.origin===location.origin&&/^\/(?:index\.html?)?$/.test(u.pathname)&&!u.search&&!u.hash;}catch{}
    const header=!!img.closest('header,[role="banner"]'),footer=!!img.closest('footer,[role="contentinfo"]');
    const identity=/\b(logo|seal|identity|brand|home)\b/i.test([img.alt,link?.getAttribute('aria-label'),link?.className].join(' '));
    const mark=home&&identity&&r.width<=160&&r.height<=160&&(header||footer);
    if(!seen.has(src))seen.set(src,[]);
    seen.get(src).push({header,footer,mark});
  }
  const duplicate_images=[],repeated_identity_marks=[];
  for(const [src,uses] of seen)if(uses.length>1){
    const record={src,uses:uses.length};
    // Only the conventional header/footer identity pair is distinguished.
    // A repeated editorial image or additional body usage remains a finding.
    if(uses.length===2&&uses.every(u=>u.mark)&&uses.some(u=>u.header)&&uses.some(u=>u.footer))repeated_identity_marks.push(record);
    else duplicate_images.push(record);
  }
  return {duplicate_images,repeated_identity_marks,images:[...seen.values()].reduce((n,a)=>n+a.length,0)};
}

export function iconCardRow(s) {
  const px=String(s.grid||'').match(/[\d.]+px/g);
  const equal=px?.length===3 ? (Math.max(...px.map(parseFloat))-Math.min(...px.map(parseFloat)))/Math.max(...px.map(parseFloat))<0.05 : /repeat\(3|1fr 1fr 1fr/.test(s.grid||'');
  return /grid/.test(s.display)&&equal&&s.icon_items===3&&s.item_count===3&&s.text_chars<600&&s.top<1400;
}

/** Classifies content roles, not successful motion. Original measurements remain reported. */
export function contentRoles(sections) {
  const stickyContent=[],inactivePanels=[];
  const visible=el=>{const r=el.getBoundingClientRect();if(r.width<=0||r.height<=0)return false;for(let n=el;n;n=n.parentElement){const s=getComputedStyle(n);if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity)<0.2)return false;}return true;};
  for(const section of sections||[]){
    if(!Number.isInteger(section.states)||section.states<2)continue;
    let roots;try{roots=document.querySelectorAll(section.selector);}catch{continue;}
    if(roots.length!==1)continue;
    const root=roots[0];if(!root.closest('main'))continue;
    for(const el of [root,...root.querySelectorAll('*')]){
      if(el.closest('dialog,[role="dialog"],[aria-modal="true"]'))continue;
      const cs=getComputedStyle(el),r=el.getBoundingClientRect(),parent=el.parentElement;
      if(cs.position==='sticky'&&/\bpinned\b/.test(section.behavior||'')&&parent&&visible(el)){
        const pr=parent.getBoundingClientRect(),ps=getComputedStyle(parent),top=Number.parseFloat(cs.top);
        // A sticky box retains normal-flow space inside its own scrolling story.
        // Fixed layers, undersized wrappers, and overflow outside the parent are
        // still overlay candidates. This does not prove pinning or transitions.
        if(!/fixed|absolute/.test(ps.position)&&Number.isFinite(top)&&pr.height>r.height*1.2&&r.left>=pr.left-1&&r.right<=pr.right+1&&r.top>=pr.top-1&&r.bottom<=pr.bottom+1&&r.height<=innerHeight-top+1)
          stickyContent.push(el);
      }
      if(el.getAttribute('aria-hidden')!=='true'||visible(el)||!parent)continue;
      const siblings=[...parent.children].filter(n=>n!==el&&n.tagName===el.tagName&&visible(n)&&n.getAttribute('aria-hidden')!=='true');
      if(!siblings.length)continue;
      const focusable=[el,...el.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]')].some(n=>!n.closest('[inert]')&&!n.disabled&&n.tabIndex>=0&&getComputedStyle(n).display!=='none'&&getComputedStyle(n).visibility!=='hidden');
      if(!focusable)inactivePanels.push(el);
    }
  }
  return {stickyContent,inactivePanels};
}

/** Actual glyph-font verification; CSS declarations do not prove font delivery. */
const trackers = new WeakMap();
export async function prepareRenderedFontDelivery(page) {
  if (trackers.has(page)) return;
  const client = await page.context().newCDPSession(page);
  const aliases = [];
  client.on('CSS.fontsUpdated', ({font}) => { if (font?.fontFamily && font?.platformFontFamily) aliases.push(font); });
  await client.send('DOM.enable');
  await client.send('CSS.enable');
  trackers.set(page, {client, aliases});
  page.once('close', () => { trackers.delete(page); client.detach().catch(() => {}); });
}

export async function auditRenderedFontDelivery(page, components) {
  const client = await page.context().newCDPSession(page);
  const findings = [];
  const records = [];
  const normalize = (value) => String(value || '').toLowerCase().trim().replace(/\s+/g, ' ');
  const generic = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-serif', 'ui-sans-serif', 'ui-monospace', 'ui-rounded', '-apple-system', 'blinkmacsystemfont']);
  try {
    await client.send('DOM.enable');
    await client.send('CSS.enable');
    const { root } = await client.send('DOM.getDocument', { depth: -1, pierce: true });
    for (const component of components) {
      const declared = String(component.family || '').split(',')[0].trim().replace(/^['"]|['"]$/g, '');
      if (!declared) continue;
      const { nodeId } = await client.send('DOM.querySelector', { nodeId: root.nodeId, selector: component.selector });
      if (!nodeId) {
        findings.push({code: 'font-target-missing', component_id: component.component_id, selector: component.selector});
        continue;
      }
      const result = await client.send('CSS.getPlatformFontsForNode', {nodeId});
      const fonts = result.fonts.filter((font) => font.glyphCount > 0);
      const hasText = await page.locator(component.selector).evaluate((element) => Boolean(element.textContent.trim()));
      const alias = await page.evaluate(async ({family, selector}) => {
        const clean = (value) => value.trim().replace(/^['"]|['"]$/g, '').toLowerCase();
        const element = document.querySelector(selector), style = getComputedStyle(element);
        const faces = await document.fonts.load(`${style.fontStyle} ${style.fontWeight} ${style.fontSize} "${family.replaceAll('"', '\\"')}"`, element.textContent);
        const loaded = faces.some((face) => face.status === 'loaded' && clean(face.family) === clean(family));
        const localFamilies = [];
        const visit = (rules) => { for (const rule of rules) {
          if (rule.type === CSSRule.FONT_FACE_RULE && clean(rule.style.fontFamily) === clean(family)) {
            for (const match of rule.style.getPropertyValue('src').matchAll(/local\(\s*(['"]?)([^)'"\n]+)\1\s*\)/g)) localFamilies.push(match[2].trim());
          }
          try { if (rule.cssRules) visit(rule.cssRules); } catch { /* browser-observed font events handle inaccessible sheets */ }
        }};
        for (const sheet of document.styleSheets) { try { visit(sheet.cssRules); } catch { /* cross-origin sheet */ } }
        return {loaded, localFamilies};
      }, {family: declared, selector: component.selector});
      const observedAliases = (trackers.get(page)?.aliases || []).filter((face) => normalize(face.fontFamily) === normalize(declared)).map((face) => face.platformFontFamily);
      const resolvedFamilies = [...new Set([...alias.localFamilies, ...observedAliases])];
      const matches = generic.has(normalize(declared)) || fonts.some((font) => normalize(font.familyName) === normalize(declared) || normalize(font.postScriptName) === normalize(declared)) ||
        alias.loaded && fonts.some((font) => resolvedFamilies.some((name) => normalize(name) === normalize(font.familyName) || normalize(name) === normalize(font.postScriptName)));
      records.push({component_id: component.component_id, selector: component.selector, declared_primary_family: declared,
        resolved_alias_families: resolvedFamilies, fonts, has_text: hasText, pass: !hasText || matches});
      if (hasText && !matches) findings.push({code: 'declared-font-not-rendered', component_id: component.component_id,
        selector: component.selector, declared_primary_family: declared, actual_families: fonts.map((font) => font.familyName),
        remedy: 'Deliver the licensed measured source family or verified matcher result; declaring its name is insufficient.'});
    }
  } catch (error) {
    findings.push({code: 'rendered-font-evidence-unavailable', message: String(error?.message || error)});
  } finally { await client.detach().catch(() => {}); }
  return {complete: !findings.length, records, findings};
}

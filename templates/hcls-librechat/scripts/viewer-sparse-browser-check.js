// Run against a newly generated isolated report, never an original saved result.
// Verifies representation behavior without changing coordinates or adding bonds.
async (page) => {
  const check = (value, message) => { if (!value) throw new Error(message); };
  let frame;
  for (const candidate of page.frames()) {
    if (await candidate.locator('#viewer-status').count()) { frame = candidate; break; }
  }
  check(frame, 'No molecular viewer');
  await frame.locator('[data-viewer-ready="true"]').waitFor();
  await frame.locator('#viewer').scrollIntoViewIfNeeded();
  const snapshot = () => {
    const atoms = models.flatMap(model => model.selectedAtoms({}));
    return {
      atoms: atoms.length,
      isolated: atoms.filter(atom => !atom.bonds?.length).length,
      isolatedVisible: atoms.filter(atom => !atom.bonds?.length && atom.style?.sphere).length,
      cartoons: atoms.filter(atom => atom.style?.cartoon).length,
      sticks: atoms.filter(atom => atom.style?.stick).length,
      geometry: JSON.stringify(atoms.map(atom => [atom.x, atom.y, atom.z, atom.bonds, atom.bondOrder])),
      style: document.getElementById('style').value,
      status: document.getElementById('viewer-status').textContent,
    };
  };
  const initial = await frame.evaluate(snapshot);
  check(initial.atoms > 0, 'Empty preview');
  check(initial.isolatedVisible === initial.isolated, 'Default style hides isolated atoms');
  if (initial.isolated === initial.atoms) check(initial.style === 'atoms', 'Bondless structure needs atom positions by default');
  const tag = new URL(page.url()).pathname.split('/').pop().replace(/[^a-z0-9_-]/gi, '-');
  await frame.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const initialScreenshot = `output/playwright/${tag}-initial.png`;
  await frame.locator('#viewer').screenshot({ path: initialScreenshot });
  const { geometry: initialGeometry, ...initialSummary } = initial;
  const results = [{ ...initialSummary, screenshot: initialScreenshot }];
  for (const style of ['sticks', 'cartoon-sticks', 'atoms']) {
    await frame.getByLabel('Molecular representation').selectOption(style);
    await frame.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const actual = await frame.evaluate(snapshot);
    check(actual.geometry === initial.geometry, 'Rendering changed coordinates or bonds');
    check(actual.isolatedVisible === actual.isolated, style + ' hides isolated atoms');
    if (style === 'cartoon-sticks' && initial.cartoons) {
      check(actual.cartoons > 0 && actual.sticks > 0, 'Additive cartoon/sticks style lost a representation');
    }
    const screenshot = `output/playwright/${tag}-${style}.png`;
    await frame.locator('#viewer').screenshot({ path: screenshot });
    const { geometry, ...summary } = actual;
    results.push({ ...summary, screenshot });
  }
  await frame.getByLabel('Molecular representation').selectOption(initial.style);
  return { results, coordinatesAndBondsPreserved: true, noReset: true };
}

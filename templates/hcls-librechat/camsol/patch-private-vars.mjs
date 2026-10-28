/** Preserve private variable bytes; explicit base64 templates make headers UTF-8 safe.
 * Build-time only. Existing raw placeholders retain their contract, with literal
 * replacement semantics. Plugin-sourced configurations remain unexpanded.
 */
import { readFile, writeFile } from 'node:fs/promises';

export function patchPrivateVars(source) {
  const old = 'value = value.replace(placeholderRegex, varVal);';
  const marker = '// scientific-private-vars-v1';
  if (source.includes(marker)) return source;
  if (source.split(old).length !== 2) throw new Error('Private variable interpolation changed; review the actual packaged implementation.');
  return source.replace(old, String.raw`${marker}
      const encodedPlaceholderRegex = new RegExp('\\{\\{' + escapedVarName + ':base64\\}\\}', 'g');
      value = value.replace(encodedPlaceholderRegex, () => Buffer.from(varVal, 'utf8').toString('base64'));
      value = value.replace(placeholderRegex, () => varVal);`);
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  const paths = process.argv.slice(2);
  if (!paths.length) throw new Error('Name the exact source and installed bundle to patch at build time.');
  for (const path of paths) {
    const old = await readFile(path, 'utf8');
    const next = patchPrivateVars(old);
    if (next !== old) await writeFile(path, next);
  }
}

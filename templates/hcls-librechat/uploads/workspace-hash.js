import { sha256 } from '@noble/hashes/sha256';

// The pinned LibreChat already supplies noble/hashes. Hash bounded slices so a
// large upload does not require a second whole-file ArrayBuffer in the browser.
export async function hashFile(file) {
  const digest = sha256.create();
  for (let offset = 0; offset < file.size; offset += 4 * 1024 * 1024) {
    digest.update(new Uint8Array(await file.slice(offset, offset + 4 * 1024 * 1024).arrayBuffer()));
  }
  return [...digest.digest()].map(value => value.toString(16).padStart(2, '0')).join('');
}

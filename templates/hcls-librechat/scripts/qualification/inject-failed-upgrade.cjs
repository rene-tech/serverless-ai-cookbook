/* Corrupt ONLY the named synthetic QA attachment after its snapshot exists.
 * The unhealthy image starts no application or MongoDB; after this receipt,
 * stop its exact endpoint to trigger the production worker's recovery path.
 */
'use strict';
const fs = require('node:fs/promises');
async function main() {
  const operation = '891d01b4-6bf3-4a44-94a9-64b6865ff938';
  if (process.env.SCIENTIFIC_STUDY_OWNER !== 'system-state-qualification-20261002' ||
      process.env.SCIENTIFIC_STATE_SNAPSHOT !== operation) throw new Error('Not the exact isolated fault candidate');
  const snapshot = await fs.stat(`/data/snapshots/${operation}.tar.gz`);
  if (snapshot.size < 1024) throw new Error('No complete pre-upgrade snapshot');
  const attachment = '/app/uploads/qa-state-20261002.txt';
  if (!(await fs.realpath(attachment)).startsWith('/data/hcls-librechat/uploads/')) throw new Error('Unexpected fixture location');
  if (!(await fs.readFile(attachment, 'utf8')).startsWith('Customer attachment')) throw new Error('Fixture already changed');
  await fs.writeFile(attachment, 'Deliberate failed-upgrade QA mutation; restore the snapshot\n');
  await fs.writeFile('/data/hcls-librechat/qa-rollback-must-remove.txt', operation);
  console.log(JSON.stringify({ operation, snapshot_bytes: snapshot.size, synthetic_attachment_changed: true }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });

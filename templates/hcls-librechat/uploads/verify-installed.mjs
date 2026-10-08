import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

// Verify the shipped image, not only the patch source or a release label.
const root = process.argv[2] || '/app';
for (const [relative, markers] of Object.entries({
  'client/src/components/Chat/Input/Files/AttachFileMenu.tsx': ['Upload file', 'selectWorkspaceFiles'],
  'client/src/components/Chat/Input/Files/MyFilesModal.tsx': ['WorkspaceFilePicker', 'Workspace files'],
  'client/src/components/SidePanel/Files/PanelTable.tsx': ['WorkspaceFilePicker', 'Earlier chat attachments'],
  'client/src/components/Chat/Input/ChatForm.tsx': ['WorkspaceAttachments', 'attachmentSend.send'],
  'client/src/components/WorkspaceFilePicker.tsx': ['next_offset', 'Upload any files to Workspace'],
  'client/src/components/MessageAttachments.tsx': ['audio', 'download'],
  'api/server/routes/scientific-demos.js': ['offset', 'limit', 'workspaceList'],
})) {
  const source = await readFile(path.join(root, relative), 'utf8');
  for (const marker of markers) assert.ok(source.includes(marker), `${relative}: missing ${marker}`);
}
const assets = path.join(root, 'client/dist/assets');
const bundles = (await Promise.all((await readdir(assets)).filter(name => name.endsWith('.js'))
  .map(name => readFile(path.join(assets, name), 'utf8')))).join('\n');
for (const marker of ['Upload file to workspace', 'Choose from Workspace', 'Workspace files', 'scientific-workspace-select', 'Refresh files']) {
  assert.ok(bundles.includes(marker), `Built browser assets omit ${marker}`);
}
console.log(JSON.stringify({workspace_uploads: true, bucket_picker: true, history_attachments: true, built_assets: true}));

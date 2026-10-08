const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const { pathToFileURL } = require('node:url');

test('integration patches match and compile the exact pinned upstream client', async () => {
  const { patchMenu, patchForm, patchMessage, patchFilesModal, patchFilesPanel } = await import(pathToFileURL(path.join(__dirname, 'patch.mjs')));
  const root = '/app/client/src/components/Chat/';
  const menu = patchMenu(fs.readFileSync(root + 'Input/Files/AttachFileMenu.tsx', 'utf8'));
  assert.match(menu, /label: 'Upload file'/);
  assert.match(menu, /label: 'Choose from Workspace'/);
  const modal = patchFilesModal(fs.readFileSync(root + 'Input/Files/MyFilesModal.tsx', 'utf8'));
  const panel = patchFilesPanel(fs.readFileSync('/app/client/src/components/SidePanel/Files/PanelTable.tsx', 'utf8'));
  for (const source of [modal, panel]) assert.match(source, /WorkspaceFilePicker/);
  assert.match(menu, /selectWorkspaceFiles\(conversation, Array.from\(event.target.files/);
  assert.match(menu, /handleFileChange\(e, toolResourceRef.current\)/);
  let form = fs.readFileSync(root + 'Input/ChatForm.tsx', 'utf8');
  form = form.replace("import AudioRecorder from './AudioRecorder';", "import AudioRecorder from './AudioRecorder';\nimport { submitWithWorkshopAudio } from '~/components/workshop-client';");
  form = form.replace('        return submitMessage(data);\n      })}', '        return submitWithWorkshopAudio(data, conversation, submitMessage);\n      })}');
  form = patchForm(form);
  assert.match(form, /attachmentSend.send\(data, submitMessage\)/);
  assert.match(form, /files.size \+ attachmentSend.count/);
  let message = fs.readFileSync(root + 'Messages/Content/Parts/Text.tsx', 'utf8');
  message = message.replace("import store from '~/store';", "import store from '~/store';\nimport { visibleWorkshopPrompt } from '~/components/workshop-client';");
  message = message.replace('const TextPart = memo(function TextPart({ text, isCreatedByUser, showCursor }: TextPartProps) {', 'const TextPart = memo(function TextPart({ text: sourceText, isCreatedByUser, showCursor }: TextPartProps) {\n  const text = isCreatedByUser ? visibleWorkshopPrompt(sourceText) : sourceText;');
  message = patchMessage(message);
  for (const source of [menu, modal, panel, form, message, fs.readFileSync(path.join(__dirname, 'attachment-only.tsx'), 'utf8')]) {
    const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX }, reportDiagnostics: true });
    assert.deepEqual(compiled.diagnostics.filter(item => item.category === ts.DiagnosticCategory.Error), []);
  }
  assert.throws(() => patchMenu(menu), /Unsupported pinned/);
});

test('pending attachment chip shows the file name and remove control without an audio section', () => {
  const source = fs.readFileSync(path.join(__dirname, 'WorkspaceAttachments.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX }, reportDiagnostics: true });
  assert.equal(compiled.diagnostics.filter(item => item.category === ts.DiagnosticCategory.Error).length, 0);
  const module = { exports: {} }, removed = [];
  vm.runInNewContext(compiled.outputText, { module, exports: module.exports, require(name) {
    if (name === 'react') return { useState: value => [value, () => {}], useEffect() {}, useRef: current => ({ current }) };
    if (name === 'librechat-data-provider') return { request: {} };
    if (name === 'react/jsx-runtime') return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
    if (name === '~/Providers') return { useChatContext: () => ({ conversation: { conversationId: 'chat' }, getMessages: () => [] }) };
    if (name === './workspace-files') return {
      bindWorkspaceFiles: () => ({ files: [{ id: 'file1', name: 'data.csv', status: 'ready' }], submitting: false }),
      subscribeWorkspaceFiles() {}, removeWorkspaceFile: (...args) => removed.push(args),
    };
    if (name === './workshop-client') return { bindAudioConversation: () => null, getAudioAttachment: () => null };
    throw new Error(name);
  } });
  const tree = module.exports.default({});
  assert.equal(tree.props['aria-label'], 'Workspace attachments');
  assert.match(JSON.stringify(tree), /data\.csv/);
  assert.doesNotMatch(JSON.stringify(tree), /Workshop audio|Play uploaded audio/);
  const chip = tree.props.children[0].props.children[0][0];
  chip.props.children.find(child => child?.type === 'button').props.onClick();
  assert.deepEqual(removed, [['chat', 'file1']]);
});

test('ordinary drag/drop and speech audio use the same single upload handler', () => {
  const sourceFiles = [path.join(__dirname, 'WorkspaceAttachments.tsx')];
  for (const workshop of [false, true]) {
    const listeners = [], effects = [], calls = [];
    const conversation = { conversationId: 'drop-chat', agent_id: workshop ? 'agent_audio_transcription_tutorial' : 'general' };
    const selectAudioAttachment = (...args) => calls.push({ kind: 'audio', args });
    for (const sourceFile of sourceFiles) {
      const module = { exports: {} };
      const compiled = ts.transpileModule(fs.readFileSync(sourceFile, 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } });
      vm.runInNewContext(compiled.outputText, { module, exports: module.exports, URL, Error,
        document: { addEventListener: (event, fn) => { if (event === 'drop') listeners.push(fn); }, removeEventListener() {} },
        require(name) {
          if (name === 'react') return { useState: value => [value, () => {}], useRef: current => ({ current }), useEffect: fn => effects.push(fn) };
          if (name === 'react/jsx-runtime') return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
          if (name === 'librechat-data-provider') return { request: {} };
          if (name === '~/Providers') return { useChatContext: () => ({ conversation, getMessages: () => [] }) };
          if (name === './workspace-files') return {
            bindWorkspaceFiles: () => null, subscribeWorkspaceFiles: () => () => {},
            selectWorkspaceFiles: (convo, files, req) => workshop && files[0].type.startsWith('audio/')
              ? selectAudioAttachment(convo.conversationId, files[0], req) : calls.push({ kind: 'workspace' }),
          };
          if (name === './workshop-client') return {
            bindAudioConversation: () => null, getAudioAttachment: () => null, isSpeechWorkshop: () => workshop,
            subscribeAudio: () => () => {}, isAudio: file => file.type.startsWith('audio/'), selectAudioAttachment,
          };
          throw new Error(name);
        },
      });
      module.exports.default({});
      effects.splice(0).forEach(fn => fn());
    }
    for (const type of ['text/csv', 'audio/wav']) {
      calls.length = 0; let stopped = false, prevented = false;
      const event = { dataTransfer: { files: [{ type, name: type === 'audio/wav' ? 'demo.wav' : 'data.csv' }] },
        preventDefault() { prevented = true; }, stopImmediatePropagation() { stopped = true; } };
      for (const listener of listeners) { listener(event); if (stopped) break; }
      assert.equal(prevented, true); assert.equal(calls.length, 1);
      assert.equal(calls[0].kind, workshop && type === 'audio/wav' ? 'audio' : 'workspace');
    }
  }
});

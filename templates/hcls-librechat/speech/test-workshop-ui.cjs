/* Compile and exercise actual TSX drop wiring with deterministic local adapters. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const { File } = require('node:buffer');
function fixture(enabled = true) {
  const calls = [], listeners = new Map(), effects = [];
  const hooks = { useState: initial => [initial, () => {}], useRef: initial => ({ current: initial }), useEffect: fn => effects.push(fn) };
  const module = { exports: {} };
  const source = fs.readFileSync(path.join(__dirname, 'SpeechWorkshop.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX }, reportDiagnostics: true });
  assert.equal(compiled.diagnostics.filter(item => item.category === ts.DiagnosticCategory.Error).length, 0);
  vm.runInNewContext(compiled.outputText, { module, exports: module.exports, URL, Error,
    document: { addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener() {} },
    require(name) {
      if (name === 'react') return hooks;
      if (name === 'react/jsx-runtime') return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
      if (name === 'librechat-data-provider') return { request: {} };
      if (name === '~/Providers') return { useChatContext: () => ({ conversation: { conversationId: 'test-chat' }, getMessages: () => [] }) };
      if (name === './workshop-client') return {
        isSpeechWorkshop: () => enabled, getAudioAttachment: () => null, bindAudioConversation: () => null,
        isAudio: file => file.type.startsWith('audio/'), subscribeAudio: () => () => {},
        selectAudioAttachment: (...args) => calls.push(args), removeAudioAttachment: () => {},
      };
      throw new Error('Unexpected dependency ' + name);
    },
  });
  const tree = module.exports.default({}); effects.forEach(fn => fn());
  return { tree, calls, drop(file) { let prevented = false; listeners.get('drop')({ dataTransfer: { files: [file] }, preventDefault() { prevented = true; }, stopImmediatePropagation() {} }); return prevented; } };
}
test('audio drop invokes only attachment selection; generic file drop is unchanged', () => {
  const f = fixture();
  assert.equal(f.drop(new File(['audio'], 'clip.wav', { type: 'audio/wav' })), true);
  assert.equal(f.calls.length, 1); assert.equal(f.calls[0][0], 'test-chat');
  assert.equal(f.drop(new File(['document'], 'note.txt', { type: 'text/plain' })), false);
  assert.equal(f.calls.length, 1);
});
test('other agents neither show the workshop panel nor intercept their uploads', () => {
  const f = fixture(false); assert.equal(f.tree, null);
  assert.equal(f.drop(new File(['audio'], 'clip.wav', { type: 'audio/wav' })), false);
  assert.equal(f.calls.length, 0);
});
test('normal chat submission alone is patched, and direct inference buttons are absent', () => {
  const patch = fs.readFileSync(path.join(__dirname, 'patch.mjs'), 'utf8');
  const component = fs.readFileSync(path.join(__dirname, 'SpeechWorkshop.tsx'), 'utf8');
  assert.match(patch, /submitWithWorkshopAudio\(data, conversation, submitMessage\)/);
  assert.match(patch, /TextPart\(\{ text: sourceText/);
  assert.match(patch, /DisplayMessage = \(\{ text: sourceText/);
  assert.equal(patch.split('const text = isCreatedByUser ? visibleWorkshopPrompt(sourceText) : sourceText;').length, 3);
  assert.doesNotMatch(component, /runSpeech|prepareAudio|onPlay=|1\. Nemotron/);
  assert.match(component, /<audio[^>]+controls/);
});

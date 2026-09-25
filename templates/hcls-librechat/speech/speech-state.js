// Pure helpers shared with deterministic tests. A partial replaces its segment;
// it is not a stream of additive tokens. Old runtime uses sequence, newer uses segment_id.
export function transcriptEvent(segments, event) {
  if (typeof event.text !== 'string') throw new Error('Invalid transcript');
  const id = String(event.segment_id ?? event.sequence ?? 'current');
  const old = segments.get(id);
  const revision = Number(event.revision ?? (old?.revision ?? -1) + 1);
  if (!old || (revision >= old.revision && !(old.final && event.type === 'transcript.partial'))) {
    segments.set(id, { text: event.text, revision, final: event.type === 'transcript.final' });
  }
  // NeMo owns whitespace and may finalize mid-word; inserting spaces between
  // segments corrupts words (e.g. "sor" + "ry") and no-space languages.
  return [...segments.values()].map((item) => item.text).join('').trim();
}
export function appendDictation(prefix, text) {
  // Preserve typed content and native ASR wording. Only avoid introducing a
  // second separator at the boundary between the existing composer and ASR.
  if (!prefix || !text) return prefix + text;
  if (/\s$/.test(prefix)) return prefix + text.trimStart();
  return prefix + (/^\s/.test(text) ? '' : ' ') + text;
}
export function wavBlob(chunks) {
  const size = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
  const header = new ArrayBuffer(44); const view = new DataView(header);
  const ascii = (offset, text) => [...text].forEach((value, index) => view.setUint8(offset + index, value.charCodeAt(0)));
  ascii(0, 'RIFF'); view.setUint32(4, 36 + size, true); ascii(8, 'WAVE'); ascii(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); ascii(36, 'data'); view.setUint32(40, size, true);
  return new Blob([header, ...chunks], { type: 'audio/wav' });
}

export function acousticWords(event) {
  // Word items omit inter-word spaces, but a chunk can begin mid-word. Partition
  // the exact final string using its acoustic items; do not guess word boundaries.
  let cursor = 0;
  const words = (event.items || []).map((word) => {
    const token = word.text.trim();
    const start = event.text.indexOf(token, cursor);
    if (!token || start < cursor) throw new Error('Acoustic items do not match the final transcript');
    const end = start + token.length;
    const result = { ...word, render_text: event.text.slice(cursor, end) };
    cursor = end; return result;
  });
  if (words.length) words[words.length - 1].render_text += event.text.slice(cursor);
  return words;
}

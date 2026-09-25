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
  return [...segments.values()].map((item) => item.text.trim()).filter(Boolean).join(' ');
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

// Pure helpers shared with deterministic tests. A partial replaces its segment;
// it is not a stream of additive tokens. Old runtime uses sequence, newer uses segment_id.
export function transcriptText(segments) {
  let text = '';
  for (const item of segments) {
    if (item.separator_before !== undefined && item.separator_before !== '' && item.separator_before !== ' ') throw new Error('Invalid native separator');
    const space = item.separator_before === ' ' && text && item.text && !/\s$/.test(text) && !/^\s/.test(item.text);
    text += (space ? ' ' : '') + item.text;
  }
  return text.trim();
}
export function transcriptEvent(segments, event) {
  if (typeof event.text !== 'string') throw new Error('Invalid transcript');
  if (event.separator_before !== undefined && (event.type !== 'transcript.final' || !['', ' '].includes(event.separator_before))) throw new Error('Invalid native separator');
  const id = String(event.segment_id ?? event.sequence ?? 'current');
  const old = segments.get(id);
  const revision = Number(event.revision ?? (old?.revision ?? -1) + 1);
  if (!old || (revision >= old.revision && !(old.final && event.type === 'transcript.partial'))) {
    segments.set(id, { text: event.text, revision, final: event.type === 'transcript.final',
      ...(event.separator_before !== undefined ? { separator_before: event.separator_before } : {}) });
  }
  // Only explicit native BPE evidence may request a boundary separator.
  // Legacy fragments, including "sor" + "ry" and no-space locales, stay verbatim.
  return transcriptText(segments.values());
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
  if (event.separator_before !== undefined && !['', ' '].includes(event.separator_before)) throw new Error('Invalid native separator');
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
  // Display metadata only; raw native item.text and acoustic times stay intact.
  if (words.length && event.separator_before === ' ' && !/^\s/.test(words[0].render_text)) words[0].render_text = ' ' + words[0].render_text;
  return words;
}

export function speakerLabel(id) {
  return id.split('+').map(part => /^speaker_[0-3]$/.test(part) ? `Speaker ${Number(part.slice(-1)) + 1}` : part === 'uncertain' ? 'Speaker uncertain' : part).join(' + ');
}
export function speakerText(turns, roles = {}) {
  return turns.map(turn => `[${roles[turn.speaker] || speakerLabel(turn.speaker)}${turn.flag ? `; ${turn.flag}` : ''}] ${turn.text}`).join('\n');
}
// This is a provisional overlap view, not a new ASR decode or guessed alignment.
// Partial text has no reliable acoustic word bounds and is always unassigned.
export function liveSpeakerTurns(segments, wordSegments, events) {
  const frames = events.flatMap(event => event.probabilities.map((p, i) => ({
    start: event.start_seconds + i * event.frame_duration_seconds,
    end: event.start_seconds + (i + 1) * event.frame_duration_seconds, p,
  })));
  const turns = [];
  let cursor = 0;
  for (const [id, segment] of segments) {
    const words = segment.final && wordSegments.get(id);
    if (!words?.length) {
      if (segment.text) turns.push({ speaker: 'uncertain', text: segment.text,
        flag: segment.final ? 'acoustic_alignment_unavailable' : 'partial_unassigned' });
      continue;
    }
    for (const word of words) {
      const start = word.start_seconds, end = word.end_seconds;
      if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) throw new Error('Invalid acoustic word timestamps');
      while (cursor < frames.length && frames[cursor].end <= start) cursor++;
      const scores = [0, 0, 0, 0]; let coverage = 0;
      for (let i = cursor; i < frames.length && frames[i].start < end; i++) {
        const frame = frames[i], overlap = Math.max(0, Math.min(end, frame.end) - Math.max(start, frame.start));
        coverage += overlap; frame.p.forEach((p, index) => { scores[index] += overlap * p; });
      }
      if (coverage) scores.forEach((p, index) => { scores[index] = p / coverage; });
      const rank = [0, 1, 2, 3].sort((a, b) => scores[b] - scores[a]);
      const active = rank.filter(i => scores[i] >= .5);
      let speaker = 'uncertain', flag = 'insufficient_or_ambiguous_activity';
      if (coverage >= (end - start) * .5 && scores[rank[0]] >= .5 && (active.length > 1 || scores[rank[0]] - scores[rank[1]] >= .1)) {
        speaker = active.length > 1 ? active.sort().map(i => `speaker_${i}`).join('+') : `speaker_${rank[0]}`;
        flag = active.length > 1 ? 'overlap' : null;
      }
      const previous = turns[turns.length - 1];
      if (previous?.speaker === speaker && previous?.flag === flag && start - previous.end_seconds < 1.5) {
        previous.text += word.render_text ?? ' ' + word.text.trim(); previous.end_seconds = end;
      } else turns.push({ speaker, flag, text: (word.render_text ?? word.text).trim(), start_seconds: start, end_seconds: end });
    }
  }
  return turns;
}

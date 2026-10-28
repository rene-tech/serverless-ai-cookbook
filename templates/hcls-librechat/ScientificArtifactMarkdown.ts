/**
 * Models sometimes attach an artifact opener to the preceding prose. Markdown
 * directives require a block boundary. Repair only that presentation boundary;
 * leave saved messages, code, quoted examples and artifact content untouched.
 */
export function normalizeArtifactMarkdown(content: string): string {
  let fence: { marker: string; length: number } | undefined;
  let inlineTicks = 0;
  return content.split(/(?<=\n)/u).map((line) => {
    const marker = /^ {0,3}(`{3,}|~{3,})([^\n]*)/u.exec(line);
    if (fence) {
      if (marker && marker[1][0] === fence.marker && marker[1].length >= fence.length
        && !marker[2].trim()) fence = undefined;
      return line;
    }
    if (!inlineTicks && marker && (marker[1][0] !== '`' || !marker[2].includes('`'))) {
      fence = { marker: marker[1][0], length: marker[1].length };
      return line;
    }
    // Indented/quoted/list examples are not top-level artifact openers.
    if (/^(?: {4}|\t| {0,3}(?:>|[-+*] |\d+[.)] ))/u.test(line)) return line;
    const opener = /(?<![:\\])(:{3,}artifact\{[^}\n]*\})[ \t]*(?:\r?\n)?$/u.exec(line);
    const boundary = opener?.index ?? line.length;
    for (let i = 0; i < boundary; i += 1) {
      if (line[i] === '\\' && !inlineTicks) { i += 1; continue; }
      if (line[i] !== '`') continue;
      let end = i + 1;
      while (line[end] === '`') end += 1;
      const length = end - i;
      if (inlineTicks === 0) inlineTicks = length;
      else if (length === inlineTicks) inlineTicks = 0;
      i = end - 1;
    }
    if (!opener || inlineTicks || !line.slice(0, boundary).trim()) return line;
    const prefix = line.slice(0, boundary);
    // Quoted literal syntax (including a quote opened on this line) stays text.
    if (/["“”]|(?:^|\s)['‘]/u.test(prefix)) return line;
    return prefix.replace(/[ \t]+$/u, '') + '\n\n' + line.slice(boundary);
  }).join('');
}

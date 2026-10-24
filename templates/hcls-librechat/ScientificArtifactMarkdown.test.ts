import { normalizeArtifactMarkdown } from './ScientificArtifactMarkdown';
import { splitMarkdownIntoBlocks } from './Chat/Messages/Content/splitMarkdown';

const header = ':::artifact{identifier="plot" type="application/vnd.react" title="Comparison"}';
const artifact = `${header}\n\`\`\`\`\nexport default function Plot() { return <div>Chart</div>; }\n\`\`\`\`\n:::`;
const parse = (content: string) => splitMarkdownIntoBlocks(normalizeArtifactMarkdown(content));

describe('artifact presentation boundaries', () => {
  it('recognizes a saved artifact attached to prose without altering its body', () => {
    expect(normalizeArtifactMarkdown(`The saved measurements.${artifact}`)).toBe(`The saved measurements.\n\n${artifact}`);
    const blocks = parse(`The saved measurements.${artifact}`);
    expect(blocks.map(block => block.artifactCount)).toEqual([0, 1]);
    expect(blocks[1].raw).toBe(artifact);
    expect(blocks.reduce((sum, block) => sum + block.codeBlockCount, 0)).toBe(0);
  });
  it('handles streamed headers and incomplete bodies using the same parser', () => {
    expect(parse(`Measured results.${header}\n\`\`\`\`\nexport default`)[1].artifactCount).toBe(1);
    expect(parse(`Measured results.${header}`)[1].artifactCount).toBe(1);
    expect(normalizeArtifactMarkdown('Measured results.:::artifact{identifier="plot"')).toBe('Measured results.:::artifact{identifier="plot"');
  });
  it.each([
    `${header}\n\`\`\`\`\nconst value = "prose.${header}";\n\`\`\`\`\n:::`,
    `\`\`\`markdown\nExample.${artifact}\n\`\`\``,
    `~~~~~markdown\nExample.${artifact}\n~~~~~`,
    `Example \`${header}\``,
    `Example \`\`literal\nText.${header}\n\`\``,
    `> Example.${header}`, `    Example.${header}`, `- Example.${header}`,
    `Example "${header}"`, `Example '${header}'`, `Example “${header}”`,
    `Example "${header}`, `Example "literal ${header}`, `Example \\${header}`,
    `Prose.\n\n${artifact}`,
  ])('preserves code, literal syntax and valid markdown: %s', input => {
    expect(normalizeArtifactMarkdown(input)).toBe(input);
  });
  it('does not consume a code block or shift subsequent artifact indices', () => {
    const blocks = parse(`Before.${artifact}\n\n\`\`\`python\nprint(1)\n\`\`\`\n\nNext.${artifact}`);
    expect(blocks.reduce((sum, block) => sum + block.artifactCount, 0)).toBe(2);
    expect(blocks.reduce((sum, block) => sum + block.codeBlockCount, 0)).toBe(1);
  });
});

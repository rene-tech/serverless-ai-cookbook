import type { Element } from 'hast';
import { workspaceCodeHref } from './WorkspaceInlineCode';

/** Runs before react-markdown's default URL sanitizer; keep its policy intact. */
export default function workspaceMarkdownLinks() {
  return (tree: { children?: unknown[] }) => {
    const walk = (node: unknown) => {
      if (!node || typeof node !== 'object') return;
      const element = node as Element;
      if (element.type === 'element' && element.tagName === 'a') {
        const href = workspaceCodeHref(element.properties?.href);
        if (href) element.properties.href = href;
      }
      if (Array.isArray(element.children)) element.children.forEach(walk);
    };
    walk(tree);
  };
}

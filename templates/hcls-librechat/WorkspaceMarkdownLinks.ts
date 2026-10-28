import type { Element } from 'hast';
import { workspaceCodeHref } from './WorkspaceInlineCode';
import { workspaceReportPath } from './WorkspaceReportPreview';

/** Runs before react-markdown's default URL sanitizer; keep its policy intact. */
export default function workspaceMarkdownLinks() {
  return (tree: { children?: unknown[] }) => {
    const walk = (node: unknown, tableReports?: Map<string, Element>) => {
      if (!node || typeof node !== 'object') return;
      const element = node as Element;
      if (element.type === 'element' && element.tagName === 'a') {
        const href = workspaceCodeHref(element.properties?.href);
        if (href) element.properties.href = href;
        if (tableReports && href && workspaceReportPath(href)
          && !element.properties['data-scientific-report-link']) {
          // Keep the original table link. Render its interactive preview after
          // the table, where it can use the conversation's available width.
          tableReports.set(href, { ...element, properties: { ...element.properties } });
          element.properties['data-scientific-report-link'] = 'true';
        }
      }
      if (Array.isArray(element.children)) {
        element.children = element.children.flatMap((child) => {
          if (!tableReports && child.type === 'element' && child.tagName === 'table') {
            const reports = new Map<string, Element>();
            walk(child, reports);
            return [child, ...Array.from(reports.values(), (link): Element => ({
              type: 'element', tagName: 'p', properties: {}, children: [link],
            }))];
          }
          walk(child, tableReports);
          return [child];
        });
      }
    };
    walk(tree);
  };
}

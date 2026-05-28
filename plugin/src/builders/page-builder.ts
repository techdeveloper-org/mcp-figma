/**
 * Page builder.
 *
 * Creates one Figma PageNode per screen definition. The caller is responsible
 * for setting figma.currentPage before appending frame children.
 */
import type { Screen } from '../types';

/** Associates a created PageNode with the Screen definition that produced it. */
export interface PageResult {
  screen: Screen;
  page: PageNode;
}

/**
 * Creates one Figma page for every screen in the provided array.
 *
 * Pages are appended to the document in the order they appear in the screens
 * array. No frame nodes are added by this function; frame creation is
 * delegated to frame-builder.ts so that page navigation and frame building
 * can be interleaved by the orchestrating importSpec function.
 *
 * @param screens - Validated screen definitions from DesignSpec.screens.
 * @returns Array of PageResult objects in the same order as the input.
 */
export function buildPages(screens: Screen[]): PageResult[] {
  const results: PageResult[] = [];

  for (const screen of screens) {
    const page = figma.createPage();
    page.name = screen.name;
    results.push({ screen, page });
  }

  return results;
}

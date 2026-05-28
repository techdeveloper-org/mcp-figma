/**
 * Frame builder.
 *
 * Creates the root FrameNode for a single screen inside the current Figma
 * page. The frame uses VERTICAL auto-layout with 16 px uniform padding and
 * 8 px item spacing, and a white background fill. All component nodes are
 * appended to this frame by the orchestrating importSpec function.
 */
import type { Screen } from '../types';

/** Associates a created FrameNode with the Screen definition that produced it. */
export interface FrameResult {
  screen: Screen;
  frame: FrameNode;
}

/**
 * Creates and configures the root frame for the given screen on the current page.
 *
 * The frame is sized to screen.width × screen.height and set up with VERTICAL
 * auto-layout so that component children stack top-to-bottom. The frame is
 * appended to figma.currentPage before returning.
 *
 * @param screen - Validated screen definition from DesignSpec.screens.
 * @returns A FrameResult linking the FrameNode to its originating Screen.
 */
export function buildFrame(screen: Screen): FrameResult {
  const frame = figma.createFrame();
  frame.name = `${screen.name}Frame`;
  frame.resize(screen.width, screen.height);
  frame.layoutMode = 'VERTICAL';
  frame.primaryAxisAlignItems = 'MIN';
  frame.counterAxisAlignItems = 'MIN';
  frame.paddingTop = 16;
  frame.paddingBottom = 16;
  frame.paddingLeft = 16;
  frame.paddingRight = 16;
  frame.itemSpacing = 8;
  frame.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 } }];
  figma.currentPage.appendChild(frame);
  return { screen, frame };
}

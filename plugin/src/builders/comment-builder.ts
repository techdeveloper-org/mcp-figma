/**
 * Comment/annotation builder.
 *
 * Appends a lightweight text annotation node to a FrameNode that lists the
 * functional requirement identifiers (FR-XXX) satisfied by the screen. This
 * annotation is visible inside the Figma canvas to help designers and
 * developers cross-reference requirements during design review.
 */
import type { Screen } from '../types';

/**
 * Appends an FR coverage annotation text node to the given frame.
 *
 * The text node is named "FR Coverage" and rendered in a 12 px medium-gray
 * style so it is visually distinct from component content. It is placed as
 * the last child of the frame so it appears at the bottom of the auto-layout
 * stack without interfering with component layout.
 *
 * @param frame - The FrameNode that owns the screen's component children.
 * @param screen - The Screen definition supplying the fr_coverage identifiers.
 */
export function buildFrameAnnotation(frame: FrameNode, screen: Screen): void {
  const textNode = figma.createText();
  textNode.name = 'FR Coverage';
  textNode.characters = `FR Coverage: ${screen.fr_coverage.join(', ')}`;
  textNode.fontSize = 12;
  textNode.fills = [{ type: 'SOLID', color: { r: 0.4, g: 0.4, b: 0.4 } }];
  frame.appendChild(textNode);
}

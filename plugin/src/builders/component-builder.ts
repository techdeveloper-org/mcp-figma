/**
 * Component builder.
 *
 * Converts a Component definition into either a Figma ComponentNode (single
 * component) or a Figma ComponentSetNode (component with variants). Layout
 * mode, size, and padding are applied via the shared applyLayout helper.
 */
import type { Component } from '../types';

/**
 * Associates a created Figma component node with the Component definition
 * that produced it. node is a ComponentSetNode when the component definition
 * contains more than one variant name, otherwise a ComponentNode.
 */
export interface ComponentResult {
  component: Component;
  node: ComponentNode | ComponentSetNode;
}

/**
 * Builds a Figma component (or component set with variants) from the given
 * Component definition.
 *
 * When component.variants is provided and contains more than one entry, each
 * variant name produces an individual ComponentNode named "ComponentName/Variant"
 * and all resulting nodes are combined into a ComponentSetNode using
 * figma.combineAsVariants. When only one variant (or no variants) is defined,
 * a plain ComponentNode is created and named directly.
 *
 * @param component - Validated component definition from DesignSpec.components.
 * @returns ComponentResult with the created node and its originating definition.
 */
export function buildComponent(component: Component): ComponentResult {
  if ((component.variants?.length ?? 0) > 1) {
    // variants is guaranteed non-null here: the length check above only
    // evaluates truthy when component.variants exists and has length > 1.
    const variantNodes: ComponentNode[] = component.variants!.map(variantName => {
      const comp = figma.createComponent();
      comp.name = `${component.name}/${variantName}`;
      applyLayout(comp, component);
      return comp;
    });

    const componentSet = figma.combineAsVariants(variantNodes, figma.currentPage);
    componentSet.name = component.name;
    return { component, node: componentSet };
  }

  const comp = figma.createComponent();
  comp.name = component.name;
  applyLayout(comp, component);
  return { component, node: comp };
}

/**
 * Applies auto-layout mode, alignment, default size, and optional padding
 * to a ComponentNode.
 *
 * When no padding is defined on the component spec, the node retains Figma's
 * default padding of zero on all sides.
 *
 * @param node - The ComponentNode to configure.
 * @param component - The source Component definition supplying layout metadata.
 */
function applyLayout(node: ComponentNode, component: Component): void {
  node.layoutMode = component.layout === 'horizontal' ? 'HORIZONTAL' : 'VERTICAL';
  node.primaryAxisAlignItems = 'CENTER';
  node.counterAxisAlignItems = 'CENTER';
  node.resize(160, 40);

  if (component.padding !== undefined) {
    node.paddingTop = component.padding.top;
    node.paddingRight = component.padding.right;
    node.paddingBottom = component.padding.bottom;
    node.paddingLeft = component.padding.left;
  }
}

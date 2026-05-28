/**
 * Unit tests for src/builders/component-builder.ts.
 *
 * Verifies single-component creation, ComponentSet creation for multi-variant
 * components, layout application, padding propagation, and the behaviour when
 * no layout or padding fields are specified.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Component } from '../src/types';

// ---------------------------------------------------------------------------
// Figma API mock
// ---------------------------------------------------------------------------

interface MockComponentNode {
  name: string;
  layoutMode: string;
  primaryAxisAlignItems: string;
  counterAxisAlignItems: string;
  width: number;
  height: number;
  paddingTop: number;
  paddingRight: number;
  paddingBottom: number;
  paddingLeft: number;
  _type: 'COMPONENT';
  resize: (w: number, h: number) => void;
}

interface MockComponentSetNode {
  name: string;
  _children: MockComponentNode[];
  _parent: unknown;
  _type: 'COMPONENT_SET';
}

let compIdCounter = 0;
const createdComponents: MockComponentNode[] = [];
let lastCombinedSet: MockComponentSetNode | null = null;

function makeMockComponent(): MockComponentNode {
  return {
    name: '',
    layoutMode: 'NONE',
    primaryAxisAlignItems: 'MIN',
    counterAxisAlignItems: 'MIN',
    width: 0,
    height: 0,
    paddingTop: 0,
    paddingRight: 0,
    paddingBottom: 0,
    paddingLeft: 0,
    _type: 'COMPONENT',
    resize(w: number, h: number) {
      this.width = w;
      this.height = h;
    },
  };
}

const figmaMock = {
  createComponent: vi.fn(() => {
    const comp = makeMockComponent();
    createdComponents.push(comp);
    return comp;
  }),
  combineAsVariants: vi.fn((nodes: MockComponentNode[], _parent: unknown): MockComponentSetNode => {
    const set: MockComponentSetNode = {
      name: '',
      _children: nodes,
      _parent,
      _type: 'COMPONENT_SET',
    };
    lastCombinedSet = set;
    return set;
  }),
  currentPage: {},
};

vi.stubGlobal('figma', figmaMock);

const { buildComponent } = await import('../src/builders/component-builder');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeComponent(overrides: Partial<Component> = {}): Component {
  return { name: 'TestButton', ...overrides };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('buildComponent — single component (no variants or one variant)', () => {
  beforeEach(() => {
    createdComponents.length = 0;
    compIdCounter = 0;
    lastCombinedSet = null;
    vi.clearAllMocks();
    figmaMock.createComponent.mockImplementation(() => {
      const comp = makeMockComponent();
      createdComponents.push(comp);
      return comp;
    });
    figmaMock.combineAsVariants.mockImplementation(
      (nodes: MockComponentNode[], _parent: unknown): MockComponentSetNode => {
        const set: MockComponentSetNode = {
          name: '',
          _children: nodes,
          _parent,
          _type: 'COMPONENT_SET',
        };
        lastCombinedSet = set;
        return set;
      }
    );
  });

  it('creates a single ComponentNode when no variants are provided', () => {
    buildComponent(makeComponent());
    expect(figmaMock.createComponent).toHaveBeenCalledTimes(1);
    expect(figmaMock.combineAsVariants).not.toHaveBeenCalled();
  });

  it('returns the component node when no variants are provided', () => {
    const result = buildComponent(makeComponent({ name: 'PrimaryButton' }));
    expect(result.node._type).toBe('COMPONENT');
  });

  it('sets the component name to component.name', () => {
    buildComponent(makeComponent({ name: 'NavBar' }));
    expect(createdComponents[0]!.name).toBe('NavBar');
  });

  it('creates a single ComponentNode when only one variant is provided', () => {
    buildComponent(makeComponent({ variants: ['Default'] }));
    expect(figmaMock.createComponent).toHaveBeenCalledTimes(1);
    expect(figmaMock.combineAsVariants).not.toHaveBeenCalled();
  });

  it('creates a single ComponentNode when variants is an empty array', () => {
    buildComponent(makeComponent({ variants: [] }));
    expect(figmaMock.createComponent).toHaveBeenCalledTimes(1);
    expect(figmaMock.combineAsVariants).not.toHaveBeenCalled();
  });

  it('returns ComponentResult with matching component definition', () => {
    const comp = makeComponent({ name: 'Avatar' });
    const result = buildComponent(comp);
    expect(result.component).toBe(comp);
  });
});

describe('buildComponent — component set with multiple variants', () => {
  beforeEach(() => {
    createdComponents.length = 0;
    lastCombinedSet = null;
    vi.clearAllMocks();
    figmaMock.createComponent.mockImplementation(() => {
      const comp = makeMockComponent();
      createdComponents.push(comp);
      return comp;
    });
    figmaMock.combineAsVariants.mockImplementation(
      (nodes: MockComponentNode[], _parent: unknown): MockComponentSetNode => {
        const set: MockComponentSetNode = {
          name: '',
          _children: nodes,
          _parent,
          _type: 'COMPONENT_SET',
        };
        lastCombinedSet = set;
        return set;
      }
    );
  });

  it('calls combineAsVariants when two variants are provided', () => {
    buildComponent(makeComponent({ variants: ['Default', 'Hover'] }));
    expect(figmaMock.combineAsVariants).toHaveBeenCalledTimes(1);
  });

  it('creates N ComponentNodes for N variants', () => {
    buildComponent(makeComponent({ variants: ['Default', 'Loading', 'Disabled'] }));
    expect(figmaMock.createComponent).toHaveBeenCalledTimes(3);
  });

  it('names each variant component as "ComponentName/VariantName"', () => {
    buildComponent(makeComponent({ name: 'Button', variants: ['Default', 'Hover'] }));
    const names = createdComponents.map(c => c.name);
    expect(names).toContain('Button/Default');
    expect(names).toContain('Button/Hover');
  });

  it('sets the ComponentSet name to component.name', () => {
    buildComponent(makeComponent({ name: 'InputField', variants: ['Empty', 'Filled', 'Error'] }));
    expect(lastCombinedSet!.name).toBe('InputField');
  });

  it('returns a node of type COMPONENT_SET', () => {
    const result = buildComponent(makeComponent({ variants: ['A', 'B'] }));
    expect(result.node._type).toBe('COMPONENT_SET');
  });

  it('passes all variant nodes to combineAsVariants', () => {
    buildComponent(makeComponent({ variants: ['V1', 'V2', 'V3'] }));
    expect(lastCombinedSet!._children).toHaveLength(3);
  });
});

describe('buildComponent — layout application', () => {
  beforeEach(() => {
    createdComponents.length = 0;
    vi.clearAllMocks();
    figmaMock.createComponent.mockImplementation(() => {
      const comp = makeMockComponent();
      createdComponents.push(comp);
      return comp;
    });
    figmaMock.combineAsVariants.mockImplementation(
      (nodes: MockComponentNode[], _parent: unknown): MockComponentSetNode => ({
        name: '',
        _children: nodes,
        _parent,
        _type: 'COMPONENT_SET',
      })
    );
  });

  it('sets layoutMode to HORIZONTAL when layout is "horizontal"', () => {
    buildComponent(makeComponent({ layout: 'horizontal' }));
    expect(createdComponents[0]!.layoutMode).toBe('HORIZONTAL');
  });

  it('sets layoutMode to VERTICAL when layout is "vertical"', () => {
    buildComponent(makeComponent({ layout: 'vertical' }));
    expect(createdComponents[0]!.layoutMode).toBe('VERTICAL');
  });

  it('sets layoutMode to VERTICAL when layout is undefined', () => {
    buildComponent(makeComponent());
    expect(createdComponents[0]!.layoutMode).toBe('VERTICAL');
  });

  it('resizes the component to 160×40', () => {
    buildComponent(makeComponent());
    expect(createdComponents[0]!.width).toBe(160);
    expect(createdComponents[0]!.height).toBe(40);
  });

  it('sets CENTER alignment on both axes', () => {
    buildComponent(makeComponent());
    expect(createdComponents[0]!.primaryAxisAlignItems).toBe('CENTER');
    expect(createdComponents[0]!.counterAxisAlignItems).toBe('CENTER');
  });
});

describe('buildComponent — padding', () => {
  beforeEach(() => {
    createdComponents.length = 0;
    vi.clearAllMocks();
    figmaMock.createComponent.mockImplementation(() => {
      const comp = makeMockComponent();
      createdComponents.push(comp);
      return comp;
    });
    figmaMock.combineAsVariants.mockImplementation(
      (nodes: MockComponentNode[], _parent: unknown): MockComponentSetNode => ({
        name: '',
        _children: nodes,
        _parent,
        _type: 'COMPONENT_SET',
      })
    );
  });

  it('applies padding when padding spec is provided', () => {
    buildComponent(makeComponent({ padding: { top: 12, right: 24, bottom: 12, left: 24 } }));
    const comp = createdComponents[0]!;
    expect(comp.paddingTop).toBe(12);
    expect(comp.paddingRight).toBe(24);
    expect(comp.paddingBottom).toBe(12);
    expect(comp.paddingLeft).toBe(24);
  });

  it('leaves padding at zero (default) when no padding is specified', () => {
    buildComponent(makeComponent());
    const comp = createdComponents[0]!;
    expect(comp.paddingTop).toBe(0);
    expect(comp.paddingRight).toBe(0);
    expect(comp.paddingBottom).toBe(0);
    expect(comp.paddingLeft).toBe(0);
  });

  it('applies asymmetric padding correctly', () => {
    buildComponent(makeComponent({ padding: { top: 4, right: 8, bottom: 16, left: 32 } }));
    const comp = createdComponents[0]!;
    expect(comp.paddingTop).toBe(4);
    expect(comp.paddingRight).toBe(8);
    expect(comp.paddingBottom).toBe(16);
    expect(comp.paddingLeft).toBe(32);
  });

  it('applies zero padding when all sides are 0', () => {
    buildComponent(makeComponent({ padding: { top: 0, right: 0, bottom: 0, left: 0 } }));
    const comp = createdComponents[0]!;
    expect(comp.paddingTop).toBe(0);
    expect(comp.paddingRight).toBe(0);
    expect(comp.paddingBottom).toBe(0);
    expect(comp.paddingLeft).toBe(0);
  });

  it('applies padding to all variant components in a component set', () => {
    buildComponent(makeComponent({
      variants: ['Default', 'Loading'],
      padding: { top: 8, right: 16, bottom: 8, left: 16 },
    }));
    for (const comp of createdComponents) {
      expect(comp.paddingTop).toBe(8);
      expect(comp.paddingLeft).toBe(16);
    }
  });
});

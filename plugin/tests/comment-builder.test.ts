/**
 * Unit tests for src/builders/comment-builder.ts.
 *
 * Verifies that buildFrameAnnotation creates a text node with the correct
 * name, characters, fontSize, fills colour, and appends it to the frame.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Screen } from '../src/types';

// ---------------------------------------------------------------------------
// Figma API mock
// ---------------------------------------------------------------------------

interface MockTextNode {
  name: string;
  characters: string;
  fontSize: number | symbol;
  fills: unknown[];
  _type: 'TEXT';
}

interface MockFrameNode {
  name: string;
  _children: MockTextNode[];
  appendChild: (child: MockTextNode) => void;
}

const createdTextNodes: MockTextNode[] = [];

function makeMockFrame(name = 'TestFrame'): MockFrameNode {
  const children: MockTextNode[] = [];
  return {
    name,
    _children: children,
    appendChild: vi.fn((child: MockTextNode) => {
      children.push(child);
    }),
  };
}

const figmaMock = {
  createText: vi.fn((): MockTextNode => {
    const node: MockTextNode = {
      name: '',
      characters: '',
      fontSize: 12,
      fills: [],
      _type: 'TEXT',
    };
    createdTextNodes.push(node);
    return node;
  }),
};

vi.stubGlobal('figma', figmaMock);

const { buildFrameAnnotation } = await import('../src/builders/comment-builder');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScreen(overrides: Partial<Screen> = {}): Screen {
  return {
    name: 'Login',
    fr_coverage: ['FR-001', 'FR-002'],
    width: 390,
    height: 844,
    components: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('buildFrameAnnotation', () => {
  beforeEach(() => {
    createdTextNodes.length = 0;
    vi.clearAllMocks();
    figmaMock.createText.mockImplementation((): MockTextNode => {
      const node: MockTextNode = {
        name: '',
        characters: '',
        fontSize: 12,
        fills: [],
        _type: 'TEXT',
      };
      createdTextNodes.push(node);
      return node;
    });
  });

  it('calls figma.createText exactly once', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(frame as unknown as FrameNode, makeScreen());
    expect(figmaMock.createText).toHaveBeenCalledTimes(1);
  });

  it('sets the text node name to "FR Coverage"', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(frame as unknown as FrameNode, makeScreen());
    expect(createdTextNodes[0]!.name).toBe('FR Coverage');
  });

  it('sets characters to "FR Coverage: FR-001, FR-002"', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(frame as unknown as FrameNode, makeScreen());
    expect(createdTextNodes[0]!.characters).toBe('FR Coverage: FR-001, FR-002');
  });

  it('lists all fr_coverage identifiers joined by ", "', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(
      frame as unknown as FrameNode,
      makeScreen({ fr_coverage: ['FR-003', 'FR-007', 'FR-012'] })
    );
    expect(createdTextNodes[0]!.characters).toBe('FR Coverage: FR-003, FR-007, FR-012');
  });

  it('handles a single fr_coverage entry without trailing comma', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(
      frame as unknown as FrameNode,
      makeScreen({ fr_coverage: ['FR-099'] })
    );
    expect(createdTextNodes[0]!.characters).toBe('FR Coverage: FR-099');
  });

  it('sets fontSize to 12', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(frame as unknown as FrameNode, makeScreen());
    expect(createdTextNodes[0]!.fontSize).toBe(12);
  });

  it('sets a medium-gray SOLID fill (r=g=b≈0.4)', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(frame as unknown as FrameNode, makeScreen());
    const fills = createdTextNodes[0]!.fills as Array<{
      type: string;
      color: { r: number; g: number; b: number };
    }>;
    expect(fills).toHaveLength(1);
    expect(fills[0]!.type).toBe('SOLID');
    expect(fills[0]!.color.r).toBeCloseTo(0.4);
    expect(fills[0]!.color.g).toBeCloseTo(0.4);
    expect(fills[0]!.color.b).toBeCloseTo(0.4);
  });

  it('appends the text node to the provided frame', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(frame as unknown as FrameNode, makeScreen());
    expect((frame.appendChild as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1);
    expect(frame._children).toHaveLength(1);
    expect(frame._children[0]).toBe(createdTextNodes[0]);
  });

  it('the appended text node is the same instance as the created text node', () => {
    const frame = makeMockFrame();
    buildFrameAnnotation(frame as unknown as FrameNode, makeScreen());
    expect(frame._children[0]).toBe(createdTextNodes[0]);
  });
});

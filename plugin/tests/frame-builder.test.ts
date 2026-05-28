/**
 * Unit tests for src/builders/frame-builder.ts.
 *
 * Verifies that buildFrame creates a FrameNode with the correct name, size,
 * auto-layout settings, padding, item spacing, and fill colour, and appends
 * it to figma.currentPage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Screen } from '../src/types';

// ---------------------------------------------------------------------------
// Figma API mock
// ---------------------------------------------------------------------------

interface MockFrame {
  name: string;
  id: string;
  width: number;
  height: number;
  layoutMode: string;
  primaryAxisAlignItems: string;
  counterAxisAlignItems: string;
  paddingTop: number;
  paddingBottom: number;
  paddingLeft: number;
  paddingRight: number;
  itemSpacing: number;
  fills: unknown[];
  _children: unknown[];
  resize: (w: number, h: number) => void;
  appendChild: (child: unknown) => void;
}

const appendedToCurrentPage: unknown[] = [];
let frameIdCounter = 0;
let currentMockFrame: MockFrame | null = null;

const figmaMock = {
  createFrame: vi.fn((): MockFrame => {
    const frame: MockFrame = {
      name: '',
      id: `frame-${++frameIdCounter}`,
      width: 0,
      height: 0,
      layoutMode: 'NONE',
      primaryAxisAlignItems: 'MIN',
      counterAxisAlignItems: 'MIN',
      paddingTop: 0,
      paddingBottom: 0,
      paddingLeft: 0,
      paddingRight: 0,
      itemSpacing: 0,
      fills: [],
      _children: [],
      resize(w: number, h: number) {
        this.width = w;
        this.height = h;
      },
      appendChild(child: unknown) {
        this._children.push(child);
      },
    };
    currentMockFrame = frame;
    return frame;
  }),
  currentPage: {
    appendChild: vi.fn((child: unknown) => {
      appendedToCurrentPage.push(child);
    }),
  },
};

vi.stubGlobal('figma', figmaMock);

const { buildFrame } = await import('../src/builders/frame-builder');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScreen(overrides: Partial<Screen> = {}): Screen {
  return {
    name: 'TestScreen',
    fr_coverage: ['FR-001'],
    width: 390,
    height: 844,
    components: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('buildFrame', () => {
  beforeEach(() => {
    appendedToCurrentPage.length = 0;
    frameIdCounter = 0;
    currentMockFrame = null;
    vi.clearAllMocks();
    figmaMock.createFrame.mockImplementation((): MockFrame => {
      const frame: MockFrame = {
        name: '',
        id: `frame-${++frameIdCounter}`,
        width: 0,
        height: 0,
        layoutMode: 'NONE',
        primaryAxisAlignItems: 'MIN',
        counterAxisAlignItems: 'MIN',
        paddingTop: 0,
        paddingBottom: 0,
        paddingLeft: 0,
        paddingRight: 0,
        itemSpacing: 0,
        fills: [],
        _children: [],
        resize(w: number, h: number) {
          this.width = w;
          this.height = h;
        },
        appendChild(child: unknown) {
          this._children.push(child);
        },
      };
      currentMockFrame = frame;
      return frame;
    });
    figmaMock.currentPage.appendChild.mockImplementation((child: unknown) => {
      appendedToCurrentPage.push(child);
    });
  });

  it('calls figma.createFrame once', () => {
    buildFrame(makeScreen());
    expect(figmaMock.createFrame).toHaveBeenCalledTimes(1);
  });

  it('names the frame as screen.name + "Frame"', () => {
    buildFrame(makeScreen({ name: 'Login' }));
    expect(currentMockFrame!.name).toBe('LoginFrame');
  });

  it('resizes the frame to screen dimensions (390×844)', () => {
    buildFrame(makeScreen({ width: 390, height: 844 }));
    expect(currentMockFrame!.width).toBe(390);
    expect(currentMockFrame!.height).toBe(844);
  });

  it('resizes correctly for a wide desktop screen (1280×900)', () => {
    buildFrame(makeScreen({ name: 'Desktop', width: 1280, height: 900 }));
    expect(currentMockFrame!.width).toBe(1280);
    expect(currentMockFrame!.height).toBe(900);
  });

  it('sets layoutMode to VERTICAL', () => {
    buildFrame(makeScreen());
    expect(currentMockFrame!.layoutMode).toBe('VERTICAL');
  });

  it('sets primaryAxisAlignItems to MIN', () => {
    buildFrame(makeScreen());
    expect(currentMockFrame!.primaryAxisAlignItems).toBe('MIN');
  });

  it('sets counterAxisAlignItems to MIN', () => {
    buildFrame(makeScreen());
    expect(currentMockFrame!.counterAxisAlignItems).toBe('MIN');
  });

  it('sets uniform 16px padding on all sides', () => {
    buildFrame(makeScreen());
    expect(currentMockFrame!.paddingTop).toBe(16);
    expect(currentMockFrame!.paddingBottom).toBe(16);
    expect(currentMockFrame!.paddingLeft).toBe(16);
    expect(currentMockFrame!.paddingRight).toBe(16);
  });

  it('sets itemSpacing to 8', () => {
    buildFrame(makeScreen());
    expect(currentMockFrame!.itemSpacing).toBe(8);
  });

  it('sets a white solid fill', () => {
    buildFrame(makeScreen());
    const fills = currentMockFrame!.fills as Array<{ type: string; color: { r: number; g: number; b: number } }>;
    expect(fills).toHaveLength(1);
    expect(fills[0]!.type).toBe('SOLID');
    expect(fills[0]!.color).toEqual({ r: 1, g: 1, b: 1 });
  });

  it('appends the frame to figma.currentPage', () => {
    buildFrame(makeScreen());
    expect(figmaMock.currentPage.appendChild).toHaveBeenCalledTimes(1);
    expect(appendedToCurrentPage[0]).toBe(currentMockFrame);
  });

  it('returns a FrameResult with the screen and frame linked', () => {
    const screen = makeScreen({ name: 'Profile' });
    const result = buildFrame(screen);
    expect(result.screen).toBe(screen);
    expect(result.frame).toBe(currentMockFrame);
  });

  it('returns a FrameResult whose frame.name matches the naming convention', () => {
    const result = buildFrame(makeScreen({ name: 'Checkout' }));
    expect(result.frame.name).toBe('CheckoutFrame');
  });
});

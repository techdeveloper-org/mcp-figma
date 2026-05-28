/**
 * Unit tests for src/builders/page-builder.ts.
 *
 * Verifies that buildPages creates one PageNode per Screen definition and
 * assigns the correct page name from screen.name.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Screen } from '../src/types';

// ---------------------------------------------------------------------------
// Figma API mock
// ---------------------------------------------------------------------------

interface MockPage {
  name: string;
  id: string;
  _type: 'PAGE';
}

let pageCounter = 0;
const createdPages: MockPage[] = [];

const figmaMock = {
  createPage: vi.fn((): MockPage => {
    const page: MockPage = { name: '', id: `page-${++pageCounter}`, _type: 'PAGE' };
    createdPages.push(page);
    return page;
  }),
};

vi.stubGlobal('figma', figmaMock);

const { buildPages } = await import('../src/builders/page-builder');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScreen(name: string): Screen {
  return {
    name,
    fr_coverage: ['FR-001'],
    width: 390,
    height: 844,
    components: [],
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('buildPages', () => {
  beforeEach(() => {
    createdPages.length = 0;
    pageCounter = 0;
    vi.clearAllMocks();
    figmaMock.createPage.mockImplementation((): MockPage => {
      const page: MockPage = { name: '', id: `page-${++pageCounter}`, _type: 'PAGE' };
      createdPages.push(page);
      return page;
    });
  });

  it('returns an empty array when given no screens', () => {
    const results = buildPages([]);
    expect(results).toHaveLength(0);
    expect(figmaMock.createPage).not.toHaveBeenCalled();
  });

  it('creates exactly one page for a single screen', () => {
    buildPages([makeScreen('Login')]);
    expect(figmaMock.createPage).toHaveBeenCalledTimes(1);
  });

  it('sets the page name to screen.name', () => {
    buildPages([makeScreen('Dashboard')]);
    expect(createdPages[0]!.name).toBe('Dashboard');
  });

  it('creates one page per screen in order', () => {
    buildPages([makeScreen('Alpha'), makeScreen('Beta'), makeScreen('Gamma')]);
    expect(createdPages.map(p => p.name)).toEqual(['Alpha', 'Beta', 'Gamma']);
  });

  it('returns PageResult with the screen and created page paired', () => {
    const screen = makeScreen('Settings');
    const results = buildPages([screen]);
    expect(results[0]!.screen).toBe(screen);
    expect(results[0]!.page.name).toBe('Settings');
  });

  it('returns correct screen-page pairs for multiple screens', () => {
    const screens = [makeScreen('A'), makeScreen('B'), makeScreen('C')];
    const results = buildPages(screens);
    results.forEach((result, idx) => {
      expect(result.screen).toBe(screens[idx]);
      expect(result.page.name).toBe(screens[idx]!.name);
    });
  });

  it('calls figma.createPage once per screen', () => {
    const screens = Array.from({ length: 5 }, (_, i) => makeScreen(`Screen${i}`));
    buildPages(screens);
    expect(figmaMock.createPage).toHaveBeenCalledTimes(5);
  });

  it('handles a screen whose name contains special characters', () => {
    buildPages([makeScreen('Screen — Übersicht (v2)')]);
    expect(createdPages[0]!.name).toBe('Screen — Übersicht (v2)');
  });
});

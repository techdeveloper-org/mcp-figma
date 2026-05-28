/**
 * Unit tests for src/builders/token-builder.ts.
 *
 * Uses a minimal Figma API mock to verify that buildTokens creates the
 * expected variable collections and variables, and that hexToRgb normalises
 * colour channels correctly. The mock is defined in-file so tests have no
 * external dependencies.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { DesignSystem } from '../src/types';

// ---------------------------------------------------------------------------
// Figma API mock
// ---------------------------------------------------------------------------

interface MockVariable {
  name: string;
  collectionId: string;
  resolvedType: string;
  valuesByMode: Record<string, unknown>;
  setValueForMode: (modeId: string, value: unknown) => void;
}

interface MockCollection {
  id: string;
  name: string;
  defaultModeId: string;
}

function makeMockCollection(name: string): MockCollection {
  return { id: `coll-${name}`, name, defaultModeId: `mode-${name}` };
}

function makeMockVariable(name: string, collection: MockCollection, resolvedType: string): MockVariable {
  const valuesByMode: Record<string, unknown> = {};
  return {
    name,
    collectionId: collection.id,
    resolvedType,
    valuesByMode,
    setValueForMode(modeId: string, value: unknown) {
      valuesByMode[modeId] = value;
    },
  };
}

const mockCollections: MockCollection[] = [];
const mockVariables: MockVariable[] = [];

const figmaMock = {
  variables: {
    createVariableCollection: vi.fn((name: string) => {
      const coll = makeMockCollection(name);
      mockCollections.push(coll);
      return coll;
    }),
    createVariable: vi.fn((name: string, collection: MockCollection, resolvedType: string) => {
      const variable = makeMockVariable(name, collection, resolvedType);
      mockVariables.push(variable);
      return variable;
    }),
  },
};

vi.stubGlobal('figma', figmaMock);

// ---------------------------------------------------------------------------
// Import module under test AFTER global is stubbed
// ---------------------------------------------------------------------------
const { buildTokens } = await import('../src/builders/token-builder');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeDesignSystem(): DesignSystem {
  return {
    colors: {
      primary: '#2563EB',
      surface: '#F8FAFC',
      error: '#DC2626',
    },
    typography: {
      body: { fontFamily: 'Inter', fontSize: 16, fontWeight: 400 },
      heading: { fontFamily: 'Inter', fontSize: 32, fontWeight: 700 },
    },
    spacing: [4, 8, 16, 24, 32],
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('buildTokens — variable collections', () => {
  beforeEach(() => {
    mockCollections.length = 0;
    mockVariables.length = 0;
    vi.clearAllMocks();
    // Re-stub to track calls freshly
    figmaMock.variables.createVariableCollection.mockImplementation((name: string) => {
      const coll = makeMockCollection(name);
      mockCollections.push(coll);
      return coll;
    });
    figmaMock.variables.createVariable.mockImplementation(
      (name: string, collection: MockCollection, resolvedType: string) => {
        const variable = makeMockVariable(name, collection, resolvedType);
        mockVariables.push(variable);
        return variable;
      }
    );
  });

  it('creates exactly three collections: Colors, Spacing, Typography', () => {
    buildTokens(makeDesignSystem());
    const names = mockCollections.map(c => c.name);
    expect(names).toContain('Colors');
    expect(names).toContain('Spacing');
    expect(names).toContain('Typography');
    expect(mockCollections.length).toBe(3);
  });

  it('calls createVariableCollection once per collection type', () => {
    buildTokens(makeDesignSystem());
    expect(figmaMock.variables.createVariableCollection).toHaveBeenCalledTimes(3);
  });
});

describe('buildTokens — color variables', () => {
  beforeEach(() => {
    mockCollections.length = 0;
    mockVariables.length = 0;
    vi.clearAllMocks();
    figmaMock.variables.createVariableCollection.mockImplementation((name: string) => {
      const coll = makeMockCollection(name);
      mockCollections.push(coll);
      return coll;
    });
    figmaMock.variables.createVariable.mockImplementation(
      (name: string, collection: MockCollection, resolvedType: string) => {
        const variable = makeMockVariable(name, collection, resolvedType);
        mockVariables.push(variable);
        return variable;
      }
    );
  });

  it('creates one COLOR variable per color token', () => {
    buildTokens(makeDesignSystem());
    const colorVars = mockVariables.filter(v => v.resolvedType === 'COLOR');
    expect(colorVars.length).toBe(3);
  });

  it('color variable names match the token keys', () => {
    buildTokens(makeDesignSystem());
    const colorNames = mockVariables.filter(v => v.resolvedType === 'COLOR').map(v => v.name);
    expect(colorNames).toContain('primary');
    expect(colorNames).toContain('surface');
    expect(colorNames).toContain('error');
  });

  it('normalises #2563EB to r≈0.145 g≈0.388 b≈0.922', () => {
    buildTokens(makeDesignSystem());
    const primaryVar = mockVariables.find(v => v.name === 'primary')!;
    const colorColl = mockCollections.find(c => c.name === 'Colors')!;
    const value = primaryVar.valuesByMode[colorColl.defaultModeId] as { r: number; g: number; b: number; a: number };
    expect(value.r).toBeCloseTo(0x25 / 255, 3);
    expect(value.g).toBeCloseTo(0x63 / 255, 3);
    expect(value.b).toBeCloseTo(0xEB / 255, 3);
    expect(value.a).toBe(1);
  });

  it('normalises #F8FAFC to near-white r≈0.973 g≈0.980 b≈0.988', () => {
    buildTokens(makeDesignSystem());
    const surfaceVar = mockVariables.find(v => v.name === 'surface')!;
    const colorColl = mockCollections.find(c => c.name === 'Colors')!;
    const value = surfaceVar.valuesByMode[colorColl.defaultModeId] as { r: number; g: number; b: number; a: number };
    expect(value.r).toBeCloseTo(0xF8 / 255, 3);
    expect(value.g).toBeCloseTo(0xFA / 255, 3);
    expect(value.b).toBeCloseTo(0xFC / 255, 3);
  });

  it('returns TokenMap.colors with an entry for every color token', () => {
    const result = buildTokens(makeDesignSystem());
    expect(Object.keys(result.colors)).toHaveLength(3);
    expect(result.colors['primary']).toBeDefined();
    expect(result.colors['surface']).toBeDefined();
    expect(result.colors['error']).toBeDefined();
  });
});

describe('buildTokens — spacing variables', () => {
  beforeEach(() => {
    mockCollections.length = 0;
    mockVariables.length = 0;
    vi.clearAllMocks();
    figmaMock.variables.createVariableCollection.mockImplementation((name: string) => {
      const coll = makeMockCollection(name);
      mockCollections.push(coll);
      return coll;
    });
    figmaMock.variables.createVariable.mockImplementation(
      (name: string, collection: MockCollection, resolvedType: string) => {
        const variable = makeMockVariable(name, collection, resolvedType);
        mockVariables.push(variable);
        return variable;
      }
    );
  });

  it('creates one FLOAT variable per spacing scale step', () => {
    buildTokens(makeDesignSystem());
    const spacingVars = mockVariables.filter(v => v.name.startsWith('spacing-'));
    expect(spacingVars.length).toBe(5);
  });

  it('names spacing variables as spacing-0, spacing-1, ... spacing-N', () => {
    buildTokens(makeDesignSystem());
    const spacingNames = mockVariables.filter(v => v.name.startsWith('spacing-')).map(v => v.name);
    expect(spacingNames).toEqual(['spacing-0', 'spacing-1', 'spacing-2', 'spacing-3', 'spacing-4']);
  });

  it('sets spacing variable values matching the spacing array', () => {
    buildTokens(makeDesignSystem());
    const spacingColl = mockCollections.find(c => c.name === 'Spacing')!;
    const spacing0 = mockVariables.find(v => v.name === 'spacing-0')!;
    expect(spacing0.valuesByMode[spacingColl.defaultModeId]).toBe(4);
    const spacing4 = mockVariables.find(v => v.name === 'spacing-4')!;
    expect(spacing4.valuesByMode[spacingColl.defaultModeId]).toBe(32);
  });

  it('returns TokenMap.spacings array matching spacing scale length', () => {
    const result = buildTokens(makeDesignSystem());
    expect(result.spacings.length).toBe(5);
  });
});

describe('buildTokens — typography variables', () => {
  beforeEach(() => {
    mockCollections.length = 0;
    mockVariables.length = 0;
    vi.clearAllMocks();
    figmaMock.variables.createVariableCollection.mockImplementation((name: string) => {
      const coll = makeMockCollection(name);
      mockCollections.push(coll);
      return coll;
    });
    figmaMock.variables.createVariable.mockImplementation(
      (name: string, collection: MockCollection, resolvedType: string) => {
        const variable = makeMockVariable(name, collection, resolvedType);
        mockVariables.push(variable);
        return variable;
      }
    );
  });

  it('creates two FLOAT variables per typography style (fontSize + fontWeight)', () => {
    buildTokens(makeDesignSystem());
    const typoVars = mockVariables.filter(
      v => v.name.endsWith('-fontSize') || v.name.endsWith('-fontWeight')
    );
    expect(typoVars.length).toBe(4); // 2 styles × 2 properties
  });

  it('creates body-fontSize and body-fontWeight variables', () => {
    buildTokens(makeDesignSystem());
    const names = mockVariables.map(v => v.name);
    expect(names).toContain('body-fontSize');
    expect(names).toContain('body-fontWeight');
  });

  it('sets body-fontSize to 16', () => {
    buildTokens(makeDesignSystem());
    const typoColl = mockCollections.find(c => c.name === 'Typography')!;
    const fontSizeVar = mockVariables.find(v => v.name === 'body-fontSize')!;
    expect(fontSizeVar.valuesByMode[typoColl.defaultModeId]).toBe(16);
  });

  it('sets heading-fontWeight to 700', () => {
    buildTokens(makeDesignSystem());
    const typoColl = mockCollections.find(c => c.name === 'Typography')!;
    const fontWeightVar = mockVariables.find(v => v.name === 'heading-fontWeight')!;
    expect(fontWeightVar.valuesByMode[typoColl.defaultModeId]).toBe(700);
  });
});

describe('buildTokens — invalid hex colour', () => {
  it('throws when a color hex is malformed', () => {
    const ds = makeDesignSystem();
    (ds.colors as Record<string, string>).bad = 'NOTAHEX';
    figmaMock.variables.createVariableCollection.mockImplementation((name: string) => {
      const coll = makeMockCollection(name);
      mockCollections.push(coll);
      return coll;
    });
    figmaMock.variables.createVariable.mockImplementation(
      (name: string, collection: MockCollection, resolvedType: string) => {
        const variable = makeMockVariable(name, collection, resolvedType);
        mockVariables.push(variable);
        return variable;
      }
    );
    expect(() => buildTokens(ds)).toThrow(/Invalid hex color/);
  });
});

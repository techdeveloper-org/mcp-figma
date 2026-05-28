/**
 * Unit tests for the runtime JSON Schema validator (src/schema.ts).
 *
 * Covers: happy-path validation, every required-field violation, invalid
 * hex color patterns, out-of-range numeric fields, invalid fontWeight enum
 * values, and malformed fr_coverage patterns.
 */
import { describe, it, expect } from 'vitest';
import { validateDesignSpec } from '../src/schema';
import type { DesignSpec } from '../src/types';

function makeValidSpec(): DesignSpec {
  return {
    _metadata: {
      generated_by: 'test-agent',
      model: 'claude-test',
      timestamp: '2026-05-28T00:00:00Z',
      schema_version: '1.0.0',
    },
    project: 'TestProject',
    design_system: {
      colors: { primary: '#2563EB', surface: '#F8FAFC' },
      typography: {
        body: { fontFamily: 'Inter', fontSize: 16, fontWeight: 400 },
        heading: { fontFamily: 'Inter', fontSize: 32, fontWeight: 700 },
      },
      spacing: [4, 8, 16, 24, 32],
    },
    screens: [
      {
        name: 'Login',
        fr_coverage: ['FR-001', 'FR-002'],
        width: 390,
        height: 844,
        components: ['LoginButton'],
      },
    ],
    components: [
      {
        name: 'LoginButton',
        variants: ['Default', 'Loading', 'Disabled'],
        layout: 'horizontal',
        padding: { top: 12, right: 24, bottom: 12, left: 24 },
      },
    ],
  };
}

describe('validateDesignSpec — happy path', () => {
  it('accepts a fully valid spec without throwing', () => {
    expect(() => validateDesignSpec(makeValidSpec())).not.toThrow();
  });

  it('accepts a minimal spec with no variants or padding on components', () => {
    const spec = makeValidSpec();
    spec.components = [{ name: 'MinimalComp' }];
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });

  it('accepts a component with layout vertical and no padding', () => {
    const spec = makeValidSpec();
    spec.components = [{ name: 'VertComp', layout: 'vertical' }];
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });

  it('accepts a component with a single variant', () => {
    const spec = makeValidSpec();
    spec.components = [{ name: 'SingleVariant', variants: ['Default'] }];
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });

  it('accepts all nine valid fontWeight values', () => {
    const weights = [100, 200, 300, 400, 500, 600, 700, 800, 900] as const;
    for (const weight of weights) {
      const spec = makeValidSpec();
      spec.design_system.typography = {
        test: { fontFamily: 'Inter', fontSize: 16, fontWeight: weight },
      };
      expect(() => validateDesignSpec(spec)).not.toThrow();
    }
  });

  it('accepts screens with empty components list', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.components = [];
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });

  it('accepts multiple screens', () => {
    const spec = makeValidSpec();
    spec.screens.push({
      name: 'Dashboard',
      fr_coverage: ['FR-003'],
      width: 1280,
      height: 900,
      components: [],
    });
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });

  it('accepts boundary width values (320 and 1920)', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.width = 320;
    expect(() => validateDesignSpec(spec)).not.toThrow();
    spec.screens[0]!.width = 1920;
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });

  it('accepts boundary height values (480 and 1440)', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.height = 480;
    expect(() => validateDesignSpec(spec)).not.toThrow();
    spec.screens[0]!.height = 1440;
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });

  it('accepts boundary fontSize values (8 and 128)', () => {
    const spec = makeValidSpec();
    spec.design_system.typography['edge'] = { fontFamily: 'Inter', fontSize: 8, fontWeight: 400 };
    expect(() => validateDesignSpec(spec)).not.toThrow();
    spec.design_system.typography['edge']!.fontSize = 128;
    expect(() => validateDesignSpec(spec)).not.toThrow();
  });
});

describe('validateDesignSpec — missing required top-level fields', () => {
  it('throws when _metadata is missing', () => {
    const spec = makeValidSpec() as Partial<DesignSpec>;
    delete spec._metadata;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when project is missing', () => {
    const spec = makeValidSpec() as Partial<DesignSpec>;
    delete spec.project;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when design_system is missing', () => {
    const spec = makeValidSpec() as Partial<DesignSpec>;
    delete spec.design_system;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when screens is missing', () => {
    const spec = makeValidSpec() as Partial<DesignSpec>;
    delete spec.screens;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when components is missing', () => {
    const spec = makeValidSpec() as Partial<DesignSpec>;
    delete spec.components;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when project is empty string', () => {
    const spec = makeValidSpec();
    (spec as unknown as Record<string, unknown>).project = '';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });
});

describe('validateDesignSpec — _metadata field violations', () => {
  it('throws when generated_by is missing', () => {
    const spec = makeValidSpec();
    delete (spec._metadata as Partial<typeof spec._metadata>).generated_by;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when model is missing', () => {
    const spec = makeValidSpec();
    delete (spec._metadata as Partial<typeof spec._metadata>).model;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when timestamp is missing', () => {
    const spec = makeValidSpec();
    delete (spec._metadata as Partial<typeof spec._metadata>).timestamp;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when schema_version is missing', () => {
    const spec = makeValidSpec();
    delete (spec._metadata as Partial<typeof spec._metadata>).schema_version;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when schema_version does not match semver pattern', () => {
    const spec = makeValidSpec();
    (spec._metadata as Record<string, unknown>).schema_version = 'v1.0.0';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when schema_version is "latest"', () => {
    const spec = makeValidSpec();
    (spec._metadata as Record<string, unknown>).schema_version = 'latest';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when _metadata has an extra property', () => {
    const spec = makeValidSpec();
    (spec._metadata as Record<string, unknown>).extra = 'nope';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });
});

describe('validateDesignSpec — design_system violations', () => {
  it('throws when colors object is empty', () => {
    const spec = makeValidSpec();
    spec.design_system.colors = {};
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when a color value uses wrong format (rgb instead of hex)', () => {
    const spec = makeValidSpec();
    (spec.design_system.colors as Record<string, string>).bad = 'rgb(0,0,0)';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when a color uses a 3-digit hex shorthand', () => {
    const spec = makeValidSpec();
    (spec.design_system.colors as Record<string, string>).short = '#FFF';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when a color has no leading #', () => {
    const spec = makeValidSpec();
    (spec.design_system.colors as Record<string, string>).nohash = 'FFFFFF';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when spacing array is empty', () => {
    const spec = makeValidSpec();
    spec.design_system.spacing = [];
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when a spacing value is negative', () => {
    const spec = makeValidSpec();
    spec.design_system.spacing = [-4, 8, 16];
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when typography entry has invalid fontWeight (e.g. 450)', () => {
    const spec = makeValidSpec();
    (spec.design_system.typography['body'] as Record<string, unknown>).fontWeight = 450;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when typography entry fontSize is below minimum (7)', () => {
    const spec = makeValidSpec();
    (spec.design_system.typography['body'] as Record<string, unknown>).fontSize = 7;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when typography entry fontSize exceeds maximum (129)', () => {
    const spec = makeValidSpec();
    (spec.design_system.typography['body'] as Record<string, unknown>).fontSize = 129;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when typography entry fontFamily is empty string', () => {
    const spec = makeValidSpec();
    (spec.design_system.typography['body'] as Record<string, unknown>).fontFamily = '';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });
});

describe('validateDesignSpec — screens violations', () => {
  it('throws when screens array is empty', () => {
    const spec = makeValidSpec();
    spec.screens = [];
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when screen name is empty', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.name = '';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when fr_coverage is empty', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.fr_coverage = [];
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when fr_coverage has an invalid pattern (FR-01 not FR-001)', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.fr_coverage = ['FR-01'];
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when fr_coverage entry lacks FR- prefix', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.fr_coverage = ['001'];
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when width is below minimum (319)', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.width = 319;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when width exceeds maximum (1921)', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.width = 1921;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when height is below minimum (479)', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.height = 479;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when height exceeds maximum (1441)', () => {
    const spec = makeValidSpec();
    spec.screens[0]!.height = 1441;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when screen has unknown extra property', () => {
    const spec = makeValidSpec();
    (spec.screens[0] as Record<string, unknown>).unknown = 'field';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });
});

describe('validateDesignSpec — components violations', () => {
  it('throws when component name is empty', () => {
    const spec = makeValidSpec();
    spec.components[0]!.name = '';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when component layout is an invalid value', () => {
    const spec = makeValidSpec();
    (spec.components[0] as Record<string, unknown>).layout = 'diagonal';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when component padding has negative top value', () => {
    const spec = makeValidSpec();
    spec.components[0]!.padding = { top: -1, right: 0, bottom: 0, left: 0 };
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when component padding is missing a required side (bottom)', () => {
    const spec = makeValidSpec();
    const paddingWithMissingBottom = { top: 0, right: 0, left: 0 };
    (spec.components[0] as Record<string, unknown>).padding = paddingWithMissingBottom;
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });

  it('throws when component has extra unknown property', () => {
    const spec = makeValidSpec();
    (spec.components[0] as Record<string, unknown>).icon = 'check';
    expect(() => validateDesignSpec(spec)).toThrow(/validation failed/);
  });
});

describe('validateDesignSpec — non-object inputs', () => {
  it('throws for null input', () => {
    expect(() => validateDesignSpec(null)).toThrow(/validation failed/);
  });

  it('throws for string input', () => {
    expect(() => validateDesignSpec('not-an-object')).toThrow(/validation failed/);
  });

  it('throws for array input', () => {
    expect(() => validateDesignSpec([])).toThrow(/validation failed/);
  });

  it('throws for number input', () => {
    expect(() => validateDesignSpec(42)).toThrow(/validation failed/);
  });

  it('throws for empty object', () => {
    expect(() => validateDesignSpec({})).toThrow(/validation failed/);
  });
});

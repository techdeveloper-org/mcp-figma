/**
 * Design token builder.
 *
 * Creates three Figma variable collections — Colors, Spacing, and Typography —
 * from the design_system section of a validated DesignSpec. All collections
 * are populated before any page or frame nodes are created so that component
 * builders can reference variables by ID if needed in future extensions.
 */
import type { DesignSystem } from '../types';

/** Maps each color token name to its created Figma Variable. */
export interface TokenMap {
  colors: Record<string, Variable>;
  spacings: Variable[];
}

/**
 * Converts a six-digit hex color string to an RGB object with components
 * normalised to the [0, 1] range expected by the Figma plugin API.
 *
 * @param hex - A hex color string in the form `#RRGGBB`.
 * @returns Object with r, g, b properties each in [0, 1].
 * @throws {Error} When the hex string does not match the expected pattern.
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (
    result === null ||
    result[1] === undefined ||
    result[2] === undefined ||
    result[3] === undefined
  ) {
    throw new Error(`Invalid hex color: ${hex}`);
  }
  return {
    r: parseInt(result[1], 16) / 255,
    g: parseInt(result[2], 16) / 255,
    b: parseInt(result[3], 16) / 255,
  };
}

/**
 * Builds all Figma variable collections from the provided design system.
 *
 * Creates a "Colors" collection with one COLOR variable per entry, a
 * "Spacing" collection with one FLOAT variable per spacing scale value,
 * and a "Typography" collection with FLOAT variables for fontSize and
 * fontWeight per typography style.
 *
 * @param designSystem - The validated design_system block from DesignSpec.
 * @returns A TokenMap with the created color and spacing variables indexed
 *   for use by downstream builders.
 */
export function buildTokens(designSystem: DesignSystem): TokenMap {
  const colorCollection = figma.variables.createVariableCollection('Colors');
  const spacingCollection = figma.variables.createVariableCollection('Spacing');
  const typographyCollection = figma.variables.createVariableCollection('Typography');

  const colorMap: Record<string, Variable> = {};

  for (const [name, hex] of Object.entries(designSystem.colors)) {
    const variable = figma.variables.createVariable(name, colorCollection, 'COLOR');
    const rgb = hexToRgb(hex);
    variable.setValueForMode(colorCollection.defaultModeId, {
      r: rgb.r,
      g: rgb.g,
      b: rgb.b,
      a: 1,
    });
    colorMap[name] = variable;
  }

  const spacingVars: Variable[] = [];
  designSystem.spacing.forEach((value, index) => {
    const variable = figma.variables.createVariable(
      `spacing-${index}`,
      spacingCollection,
      'FLOAT'
    );
    variable.setValueForMode(spacingCollection.defaultModeId, value);
    spacingVars.push(variable);
  });

  for (const [name, spec] of Object.entries(designSystem.typography)) {
    const fontSizeVar = figma.variables.createVariable(
      `${name}-fontSize`,
      typographyCollection,
      'FLOAT'
    );
    fontSizeVar.setValueForMode(typographyCollection.defaultModeId, spec.fontSize);

    const fontWeightVar = figma.variables.createVariable(
      `${name}-fontWeight`,
      typographyCollection,
      'FLOAT'
    );
    fontWeightVar.setValueForMode(typographyCollection.defaultModeId, spec.fontWeight);
  }

  return { colors: colorMap, spacings: spacingVars };
}

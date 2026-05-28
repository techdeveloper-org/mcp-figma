/**
 * Vitest configuration for the Design Spec Importer plugin test suite.
 *
 * Coverage is collected via v8 with 100% thresholds on all metrics.
 * The Figma plugin entry point (code.ts) is excluded from direct coverage
 * because it depends on the figma global at module scope and is exercised
 * via integration testing outside the unit test harness.
 */
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.ts'],
      exclude: [
        'src/code.ts',
        'src/ui.html',
      ],
      thresholds: {
        lines: 100,
        functions: 100,
        branches: 100,
        statements: 100,
      },
    },
  },
});

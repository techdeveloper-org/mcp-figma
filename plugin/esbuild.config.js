import * as esbuild from 'esbuild';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const isWatch = process.argv.includes('--watch');
const pkg = JSON.parse(readFileSync(join(__dirname, 'package.json'), 'utf8'));

/** @type {import('esbuild').BuildOptions} */
const buildOptions = {
  entryPoints: ['src/code.ts'],
  bundle: true,
  outfile: 'dist/code.js',
  platform: 'browser',
  target: 'es2017',
  format: 'iife',
  external: [],
  minifyWhitespace: false,
  minifySyntax: false,
  sourcemap: true,
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  logLevel: 'info',
  metafile: true,
};

if (isWatch) {
  const ctx = await esbuild.context(buildOptions);
  await ctx.watch();
  console.log(`[Design Spec Importer v${pkg.version}] Watching for changes...`);
} else {
  const result = await esbuild.build(buildOptions);
  const outputFile = result.metafile?.outputs?.['dist/code.js'];
  const bytes = outputFile?.bytes ?? 0;
  console.log(`[Design Spec Importer v${pkg.version}] Plugin bundle built: dist/code.js (${(bytes / 1024).toFixed(1)} KB)`);
}

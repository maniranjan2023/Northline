#!/usr/bin/env node
/**
 * Render all Voyager archify diagrams to HTML + README-ready SVG/PNG assets.
 * Usage: node docs/diagrams/render-diagrams.mjs
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const archifyCli = path.join(
  process.env.USERPROFILE || process.env.HOME || '',
  '.agents/skills/archify/bin/archify.mjs'
);
const archifyDir = path.join(__dirname, 'archify');
const htmlDir = path.join(__dirname, 'html');
const svgDir = path.join(__dirname, 'svg');
const pngDir = path.join(__dirname, 'png');
const assetsPngDir = path.join(__dirname, '../../assets/diagrams');

const DIAGRAMS = [
  { json: 'voyager-system.architecture.json', html: 'voyager-system.html', base: 'voyager-system' },
  { json: 'voyager-user-flow.workflow.json', html: 'voyager-user-flow.html', base: 'voyager-user-flow' },
  { json: 'voyager-memory.dataflow.json', html: 'voyager-memory.html', base: 'voyager-memory' },
  { json: 'voyager-guardrails.sequence.json', html: 'voyager-guardrails.html', base: 'voyager-guardrails' },
  { json: 'voyager-observability.sequence.json', html: 'voyager-observability.html', base: 'voyager-observability' },
  { json: 'voyager-evals.workflow.json', html: 'voyager-evals.html', base: 'voyager-evals' },
];

function typeFromFilename(filename) {
  if (filename.includes('.architecture.')) return 'architecture';
  if (filename.includes('.workflow.')) return 'workflow';
  if (filename.includes('.sequence.')) return 'sequence';
  if (filename.includes('.dataflow.')) return 'dataflow';
  if (filename.includes('.lifecycle.')) return 'lifecycle';
  throw new Error(`Unknown diagram type for ${filename}`);
}

function parseCssVariables(block) {
  const vars = {};
  for (const match of block.matchAll(/--([a-zA-Z0-9-]+)\s*:\s*([^;]+);/g)) {
    vars[`--${match[1]}`] = match[2].trim();
  }
  return vars;
}

function varsToCss(vars) {
  return Object.entries(vars)
    .map(([name, value]) => `${name}: ${value};`)
    .join(' ');
}

function extractDarkVars(html) {
  const match = html.match(/:root,\s*\[data-theme="dark"\]\s*\{([^}]+)\}/s);
  if (!match) throw new Error('Dark theme CSS block not found in HTML');
  return parseCssVariables(match[1]);
}

function extractLightVars(html) {
  const match = html.match(/\[data-theme="light"\]\s*\{([^}]+)\}/s);
  if (!match) throw new Error('Light theme CSS block not found in HTML');
  return parseCssVariables(match[1]);
}

function extractSemanticCss(html) {
  const marker = 'SVG SEMANTIC CLASSES';
  const start = html.indexOf(marker);
  const end = html.indexOf('Optional trace animation');
  if (start < 0 || end < 0) throw new Error('Semantic CSS block not found in HTML');
  const closeComment = html.indexOf('*/', start);
  const block = html.slice(closeComment + 2, end);
  const rules = [];
  for (const match of block.matchAll(/(\.[a-zA-Z0-9_-]+(?:\s*,\s*\.[a-zA-Z0-9_-]+)*)\s*\{([^}]+)\}/g)) {
    const selector = match[1].trim();
    if (/^\.(?:c|t|a|m)-/.test(selector)) {
      rules.push(`${selector} { ${match[2].trim()} }`);
    }
  }
  return rules.join('\n');
}

/**
 * Build a self-contained dual-theme SVG (Archify export semantics) so README
 * hosts can render colors without the parent HTML stylesheet.
 */
function extractStandaloneSvg(htmlPath, svgPath) {
  const html = fs.readFileSync(htmlPath, 'utf8');
  const svgMatch = html.match(/<div class="diagram-container">\s*(<svg[\s\S]*?<\/svg>)/);
  if (!svgMatch) throw new Error(`No diagram SVG found in ${htmlPath}`);

  const darkVars = extractDarkVars(html);
  const lightVars = extractLightVars(html);
  const hostStyle = extractSemanticCss(html);

  const svg = svgMatch[1];
  const vbMatch = svg.match(/viewBox="([^"]+)"/);
  if (!vbMatch) throw new Error(`No viewBox in SVG from ${htmlPath}`);
  const [, , w, h] = vbMatch[1].split(/\s+/).map(Number);

  const clone = svg
    .replace(/\sdata-theme="[^"]*"/, '')
    .replace(
      /<svg\b/,
      `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"`
    );

  const fontFallback = [400, 500, 600, 700]
    .map(
      (wgt) =>
        `@font-face { font-family: 'JetBrains Mono'; font-weight: ${wgt}; src: local('JetBrains Mono'), local('JetBrainsMono-Regular'); }`
    )
    .join('\n');

  const style = [
    fontFallback,
    "svg { font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }",
    hostStyle,
    `:root, svg { ${varsToCss(darkVars)} }`,
    `@media (prefers-color-scheme: light) { :root, svg { ${varsToCss(lightVars)} } }`,
    `svg[data-theme="light"] { ${varsToCss(lightVars)} }`,
    `svg[data-theme="dark"] { ${varsToCss(darkVars)} }`,
    'rect.c-bg-rect { fill: var(--bg); }',
  ].join('\n');

  const standalone = clone.replace(
    /<svg[^>]*>/,
    (open) =>
      `${open}\n<style>\n${style}\n</style>\n<rect class="c-bg-rect" width="100%" height="100%"/>`
  );

  fs.writeFileSync(svgPath, standalone, 'utf8');
}

async function exportPngAssets() {
  let chromium;
  try {
    ({ chromium } = await import('playwright'));
  } catch {
    console.warn('Playwright not installed — skipping PNG export. Run: npx playwright install chromium');
    return false;
  }

  const browser = await chromium.launch();
  try {
    for (const d of DIAGRAMS) {
      const htmlPath = path.join(htmlDir, d.html);
      const pngPath = path.join(pngDir, `${d.base}.png`);
      const assetsPngPath = path.join(assetsPngDir, `${d.base}.png`);
      const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
      await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'load' });
      await page.waitForSelector('.diagram-container svg');
      const box = await page.locator('.diagram-container').boundingBox();
      if (!box) throw new Error(`Could not measure diagram container in ${d.html}`);
      await page.locator('.diagram-container').screenshot({ path: assetsPngPath, type: 'png' });
      fs.copyFileSync(assetsPngPath, pngPath);
      await page.close();
      console.log(`  -> ${d.base}.png (+ assets/diagrams/)`);
    }
    return true;
  } finally {
    await browser.close();
  }
}

fs.mkdirSync(htmlDir, { recursive: true });
fs.mkdirSync(svgDir, { recursive: true });
fs.mkdirSync(pngDir, { recursive: true });
fs.mkdirSync(assetsPngDir, { recursive: true });

let failed = 0;
for (const d of DIAGRAMS) {
  const input = path.join(archifyDir, d.json);
  const output = path.join(htmlDir, d.html);
  const svgOut = path.join(svgDir, `${d.base}.svg`);
  const type = typeFromFilename(d.json);

  console.log(`Rendering ${d.json} ...`);
  const validate = spawnSync(process.execPath, [archifyCli, 'validate', type, input], {
    encoding: 'utf8',
  });
  if (validate.status !== 0) {
    console.error(validate.stdout || validate.stderr);
    failed++;
    continue;
  }

  const render = spawnSync(process.execPath, [archifyCli, 'render', type, input, output], {
    encoding: 'utf8',
  });
  if (render.status !== 0) {
    console.error(render.stdout || render.stderr);
    failed++;
    continue;
  }

  try {
    extractStandaloneSvg(output, svgOut);
    console.log(`  -> ${d.html} + ${d.base}.svg`);
  } catch (err) {
    console.error(`  SVG export failed for ${d.html}: ${err.message}`);
    failed++;
  }
}

if (failed) {
  console.error(`\n${failed} diagram(s) failed.`);
  process.exit(1);
}

console.log('\nExporting PNG previews for README embedding ...');
const pngOk = await exportPngAssets();
if (!pngOk) {
  console.warn('PNG export skipped — README will use standalone SVG only.');
}

console.log('\nAll diagrams rendered successfully.');

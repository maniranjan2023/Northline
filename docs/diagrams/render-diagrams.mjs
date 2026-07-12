#!/usr/bin/env node
/**
 * Render all Voyager archify diagrams to HTML + extract SVG for README embedding.
 * Usage: node docs/diagrams/render-diagrams.mjs
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '../..');
const archifyCli = path.join(
  process.env.USERPROFILE || process.env.HOME || '',
  '.agents/skills/archify/bin/archify.mjs'
);
const archifyDir = path.join(__dirname, 'archify');
const htmlDir = path.join(__dirname, 'html');
const svgDir = path.join(__dirname, 'svg');

const DIAGRAMS = [
  { json: 'voyager-system.architecture.json', html: 'voyager-system.html', svg: 'voyager-system.svg' },
  { json: 'voyager-user-flow.workflow.json', html: 'voyager-user-flow.html', svg: 'voyager-user-flow.svg' },
  { json: 'voyager-memory.dataflow.json', html: 'voyager-memory.html', svg: 'voyager-memory.svg' },
  { json: 'voyager-guardrails.sequence.json', html: 'voyager-guardrails.html', svg: 'voyager-guardrails.svg' },
  { json: 'voyager-observability.sequence.json', html: 'voyager-observability.html', svg: 'voyager-observability.svg' },
  { json: 'voyager-evals.workflow.json', html: 'voyager-evals.html', svg: 'voyager-evals.svg' },
];

function typeFromFilename(filename) {
  if (filename.includes('.architecture.')) return 'architecture';
  if (filename.includes('.workflow.')) return 'workflow';
  if (filename.includes('.sequence.')) return 'sequence';
  if (filename.includes('.dataflow.')) return 'dataflow';
  if (filename.includes('.lifecycle.')) return 'lifecycle';
  throw new Error(`Unknown diagram type for ${filename}`);
}

function extractSvg(htmlPath, svgPath) {
  const html = fs.readFileSync(htmlPath, 'utf8');
  const match = html.match(/<svg[\s\S]*?<\/svg>/);
  if (!match) throw new Error(`No SVG found in ${htmlPath}`);
  fs.writeFileSync(svgPath, match[0], 'utf8');
}

fs.mkdirSync(htmlDir, { recursive: true });
fs.mkdirSync(svgDir, { recursive: true });

let failed = 0;
for (const d of DIAGRAMS) {
  const input = path.join(archifyDir, d.json);
  const output = path.join(htmlDir, d.html);
  const svgOut = path.join(svgDir, d.svg);
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

  extractSvg(output, svgOut);
  console.log(`  -> ${d.html} + ${d.svg}`);
}

if (failed) {
  console.error(`\n${failed} diagram(s) failed.`);
  process.exit(1);
}
console.log('\nAll diagrams rendered successfully.');

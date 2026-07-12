# Voyager AI — Architecture Diagrams

Visual diagrams for system architecture, user flow, memory, guardrails, observability, and evals. Built with [Archify](https://github.com/archify) JSON definitions and rendered to SVG for README embedding.

## Diagrams

| Diagram | Type | Source JSON | SVG |
|---------|------|-------------|-----|
| System architecture | architecture | [`archify/voyager-system.architecture.json`](archify/voyager-system.architecture.json) | [`svg/voyager-system.svg`](svg/voyager-system.svg) |
| User flow | workflow | [`archify/voyager-user-flow.workflow.json`](archify/voyager-user-flow.workflow.json) | [`svg/voyager-user-flow.svg`](svg/voyager-user-flow.svg) |
| Memory flow | dataflow | [`archify/voyager-memory.dataflow.json`](archify/voyager-memory.dataflow.json) | [`svg/voyager-memory.svg`](svg/voyager-memory.svg) |
| Guardrails flow | sequence | [`archify/voyager-guardrails.sequence.json`](archify/voyager-guardrails.sequence.json) | [`svg/voyager-guardrails.svg`](svg/voyager-guardrails.svg) |
| Observability flow | sequence | [`archify/voyager-observability.sequence.json`](archify/voyager-observability.sequence.json) | [`svg/voyager-observability.svg`](svg/voyager-observability.svg) |
| Evaluation flow | workflow | [`archify/voyager-evals.workflow.json`](archify/voyager-evals.workflow.json) | [`svg/voyager-evals.svg`](svg/voyager-evals.svg) |

## Where diagrams are embedded

| README | Diagrams |
|--------|----------|
| [`README.md`](../../README.md) | All six |
| [`memory/README.md`](../../memory/README.md) | Memory |
| [`guardrails/README.md`](../../guardrails/README.md) | Guardrails |
| [`evals/README.md`](../../evals/README.md) | Evals |
| [`docs/LANGSMITH.md`](../LANGSMITH.md) | Observability |

## Regenerate

From the project root:

```powershell
node docs/diagrams/render-diagrams.mjs
```

This writes:

- `docs/diagrams/html/*.html` — interactive Archify pages (export PNG from browser menu)
- `docs/diagrams/svg/*.svg` — static assets used in README files

**Requirements:** Node.js 18+ and the Archify skill installed at `~/.agents/skills/archify/` (used by the render script).

## Edit a diagram

1. Edit the JSON under `docs/diagrams/archify/`
2. Run `node docs/diagrams/render-diagrams.mjs`
3. Commit both the JSON and updated SVG files

If validation fails, the script prints layout hints (label overlap, node collision, etc.) — adjust `col`, `yOffset`, `labelAt`, or lane placement in the JSON.

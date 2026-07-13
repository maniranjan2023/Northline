# Northline — Frontend

All user-facing UI lives here: React + TypeScript + Vite.

## Pages

- `/` — travel chat, agent pipeline, improvement audit, feedback
- `/admin` — human review for trace proposals, lesson book, candidates, audit events

## Development

```powershell
npm install
npm run dev
```

## Production build

```powershell
npm run build
```

Serve `dist/` behind your API or set `VITE_API_BASE` to the backend URL.

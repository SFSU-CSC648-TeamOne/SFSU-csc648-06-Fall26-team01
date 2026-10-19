# Section 4 -- High-level System Architecture

Source: `SFSU-CSC648-TeamOne/SFSU-csc648-06-Fall26-team01`, `main`, Git tree `8b2a61d5905f8721f7dd63f351e08777b45cb3a0`.

## Implemented component / dependency diagram

```mermaid
flowchart LR
  User[Website visitor] --> Hosting[Vercel — deployment target]
  Repo[GitHub main] -->|frontend push| Actions[GitHub Actions — deploy-vercel.yml]
  Actions -->|vercel deploy --prod| Hosting
  subgraph Frontend[Next.js frontend — app/frontend]
    Layout[RootLayout / global CSS]
    Home[HomePage /]
    About[AboutPage /about]
    Model[ModelViewer — React Three Fiber / Drei]
    Data[In-memory exercise / feature / progress examples]
    Media[public/about assets — GLB / MP4 / legacy HTML]
    Layout -.-> Home
    Layout -.-> About
    Home --> Model
    Home --> Data
    Home -->|video src| Media
    Model -->|useGLTF| Media
    Home <-->|Next Link| About
  end
  Hosting --> Home
  Hosting --> About
  Legacy[Legacy deploy-about.yml] -.->|outdated source app/frontend/about| Media
```

**Evidence:** `app/frontend/app/page.tsx` imports `ModelViewer` and defines hardcoded `features` and `exercises` arrays; `app/frontend/app/about/ModelViewer.tsx` loads a `.glb` asset via Drei; `app/frontend/app/layout.tsx` imports `globals.css`; GitHub Actions `deploy-vercel.yml` invokes Vercel CLI. The `deploy-about.yml` workflow uses `app/frontend/about/*`, a source directory missing on current main. These are code/configuration relationships, not proof of live deployment availability.

## Documented target design (not implemented)

```mermaid
flowchart LR
  User[User] --> UI[Next.js frontend — existing]
  UI -.->|planned API calls| API[Python FastAPI — planned]
  API -.->|planned ORM access| DB[(Supabase PostgreSQL — planned)]
  API -.->|planned personalized functionality| AI[AI integration — TBD]
```

The README lists Python, FastAPI, SQLAlchemy and Supabase/PostgreSQL as the intended stack. `app/backend` contains only `.gitkeep`. No runtime API calls or database client imports were identified in the inspected Next.js route and component files. The target diagram must not be interpreted as running functionality.

## Caveats

- The legacy HTML in `app/frontend/index.html` and `public/about/**/*.html` is separate from Next.js App Router pages.
- Repository configuration shows an intended deployment path, not verified deployment health.
- The Mermaid file and corresponding UML component `.puml` files should be updated after new backend/API components are merged.
- To preview `.puml` in VS Code, install the PlantUML extension; `architecture.md` previews with the built-in Markdown preview (`Ctrl+K`, then `V`).

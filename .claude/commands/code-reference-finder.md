---
name: code-reference-finder
description: Find useful code references during development. Use when developer needs implementation examples, patterns, or wants to see how others solved similar problems. Triggers on "find examples of", "how do others implement", "show me similar projects", "find reference implementations", "what's the best practice for", or when external references would help.
---

# Code Reference Finder

Help developers find useful code references. Show them options, let them choose.

## Core Philosophy

- **Inform, don't gatekeep** — Note characteristics, don't hide results
- **More options = more control** — Show 5-10 results, not just 3
- **Simple can be better** — A clear 50-line example beats a 5000-line "proper" implementation for learning
- **"Old" doesn't mean bad** — Stable code that works is still useful
- **User knows their context** — They'll pick what fits

## Workflow

### Step 1: Understand the Request

| Need Type | Signs | Approach |
|-----------|-------|----------|
| **Quick snippet** | "how do I...", specific function | Code search, show multiple files |
| **Pattern/structure** | "best way to...", architecture | Repo search, show directory layouts |
| **Integration** | "connect X with Y" | Search both terms, focus on config |
| **Learning example** | "example of...", student context | Include tutorials, demos, small repos |
| **Production reference** | "production-grade", scale concerns | Note which repos have tests/CI |

If unclear, ask: "Looking for a quick snippet or a fuller example to study?"

### Step 2: Search Effectively

**Query formula:** `[what] + [technology] + [context]`

Examples:
- "nextauth session callback typescript"
- "express middleware error handling"
- "react useEffect cleanup async"

**Don't over-filter.** Skip these unless user specifically wants production code:
- `stars:>100` — cuts out useful small projects
- `pushed:>2024-01-01` — old code can still be perfect
- `-example -demo -tutorial` — these are often exactly what learners need

**Do use:**
- `language:typescript` or `language:python` — match their stack
- `path:src` or `path:lib` — find implementation, not tests
- `extension:tsx` or `extension:py` — file type filtering

### Step 3: Present Results with Context

Show **5-10 results** with honest notes. Let user pick.

**Template for each result:**
```
**[Repo/File Name]** — [one-line description]
[stars] | Last updated: [date] | [size/complexity note]

[Why it might be useful for their specific question]

[Link to specific file/line]

Notes: [Any relevant context - old but clean, complex but complete, simple but limited, etc.]
```

**Priority ordering (not filtering):**

1. **Best for learning** — Clean, small, focused, well-commented
2. **Best for copying** — Modern stack match, working code, minimal dependencies
3. **Best for understanding patterns** — Good structure, clear separation
4. **Production references** — Has tests, CI, active maintenance
5. **Historical/educational** — Older but pedagogically valuable

### Step 4: Add Useful Context (Not Judgments)

**Note these characteristics, don't use them to exclude:**

| Characteristic | What to say |
|---------------|-------------|
| Last commit 2+ years ago | "Older codebase, but the pattern still applies" |
| No tests | "No test files visible" (neutral, not negative) |
| Small/simple | "Minimal implementation, good for understanding the core idea" |
| Large/complex | "Full-featured, might be more than you need" |
| Tutorial repo | "Explicitly educational, has explanations" |
| Few stars | "Lesser known but solves the problem" |
| Many stars | "Popular, well-documented" |
| Uses older syntax | "Uses [older pattern], you'd adapt to [newer equivalent]" |

### Step 5: Help Them Use What They Found

After showing options:
- Offer to explain any of the results in detail
- Offer to extract the specific relevant code
- Offer to adapt the pattern to their stack
- Answer follow-up questions

---

## Search Patterns by Scenario

### Authentication & Authorization

**OAuth/Social Login:**
```
grep.app: "NextAuth" "providers" path:auth language:typescript
github: topic:nextauth topic:prisma stars:>50 pushed:>2024-01-01
```

**JWT Implementation:**
```
grep.app: "jsonwebtoken" "verify" "sign" language:typescript -test
github: topic:jwt topic:express stars:>100
```

**Session Management:**
```
grep.app: "express-session" "cookie" "secure" path:middleware
grep.app: "iron-session" path:lib language:typescript
```

### Database Patterns

**Prisma Patterns:**
```
grep.app: "prisma.client" "$transaction" language:typescript
grep.app: "PrismaClient" "middleware" path:lib
```

**Drizzle ORM:**
```
grep.app: "drizzle-orm" "pgTable" language:typescript
github: topic:drizzle topic:postgres stars:>30
```

**MongoDB/Mongoose:**
```
grep.app: "mongoose.Schema" "pre" "post" path:models
grep.app: "mongoose" "aggregate" "$lookup" language:typescript
```

### API Design

**REST with Express:**
```
grep.app: "express.Router" "async" path:routes language:typescript
grep.app: "express" "middleware" "error" "next" path:src
```

**tRPC:**
```
grep.app: "createTRPCRouter" "procedure" language:typescript
```

**GraphQL:**
```
grep.app: "@Resolver" "Query" "Mutation" language:typescript
grep.app: "makeExecutableSchema" "typeDefs" "resolvers"
```

### React Patterns

**Server Components (App Router):**
```
grep.app: "use server" "async" path:app language:typescript
grep.app: "cookies()" "headers()" path:app/api
```

**State Management:**
```
grep.app: "zustand" "create" "persist" language:typescript
grep.app: "useReducer" "dispatch" path:hooks
```

**Custom Hooks:**
```
grep.app: "export function use" path:hooks language:typescript -test
grep.app: "useState" "useEffect" "useCallback" path:hooks
```

**Form Handling:**
```
grep.app: "react-hook-form" "useForm" "register" language:tsx
grep.app: "zod" "zodResolver" "useForm" language:typescript
```

### Testing

**Unit Tests (Vitest/Jest):**
```
grep.app: "describe" "it" "expect" "vi.mock" language:typescript path:test
grep.app: "beforeEach" "afterEach" "mock" path:__tests__
```

**E2E (Playwright):**
```
grep.app: "test" "page" "expect" "locator" path:e2e language:typescript
```

**API Testing:**
```
grep.app: "supertest" "request" "expect" path:test language:typescript
```

### DevOps & Infrastructure

**Docker:**
```
grep.app: "FROM node" "WORKDIR" "COPY" extension:dockerfile
grep.app: "docker-compose" "services" "volumes" extension:yml path:docker
```

**GitHub Actions:**
```
grep.app: "uses:" "run:" path:.github/workflows extension:yml
grep.app: "actions/checkout" "pnpm" "test" path:.github
```

### Error Handling & Logging

**Error Boundaries:**
```
grep.app: "ErrorBoundary" "componentDidCatch" language:tsx
grep.app: "error.tsx" "reset" path:app
```

**Structured Logging:**
```
grep.app: "pino" "logger" "child" language:typescript
grep.app: "winston" "createLogger" "transports"
```

### File Handling

**Upload/Download:**
```
grep.app: "multer" "upload" "single" language:typescript
grep.app: "@uploadthing" path:src language:typescript
```

**S3/Cloud Storage:**
```
grep.app: "S3Client" "PutObjectCommand" language:typescript
grep.app: "@aws-sdk/client-s3" "getSignedUrl"
```

### Real-time Features

**WebSockets:**
```
grep.app: "socket.io" "emit" "on" path:server language:typescript
grep.app: "ws" "WebSocket" "onmessage" language:typescript
```

**Server-Sent Events:**
```
grep.app: "ReadableStream" "TextEncoder" "event:" path:api
grep.app: "EventSource" path:hooks language:typescript
```

---

## Pattern Extraction Guide

### Directory Structure Reading

**Next.js App Router:**
```
app/
├── (auth)/              # Route groups
│   ├── login/page.tsx
│   └── register/page.tsx
├── api/                 # API routes
│   └── [resource]/route.ts
├── layout.tsx           # Root layout
└── page.tsx             # Home page
```
Key files: `layout.tsx`, `page.tsx`, `route.ts`

**Express/Node Backend:**
```
src/
├── routes/              # HTTP handlers
├── controllers/         # Business logic
├── middleware/          # Request processing
├── services/            # External integrations
├── models/              # Data models
└── utils/               # Helpers
```
Key files: `routes/index.ts`, `middleware/*.ts`

### Where to Look First

| User Needs | Look In |
|------------|---------|
| API endpoint logic | `routes/`, `api/`, `handlers/` |
| React component | `components/`, `app/`, `pages/` |
| Database queries | `services/`, `repositories/`, `db/` |
| Configuration | Root config files, `config/` |
| Custom hooks | `hooks/`, `lib/hooks/` |
| Utilities | `utils/`, `lib/`, `helpers/` |
| Types/interfaces | `types/`, `*.d.ts`, co-located with features |

### Extraction Templates

**Snippet Extraction (< 50 lines):**
```markdown
## [What this does]

From: [repo/file:line-range]

[code block]

**Key points:**
- [Explain non-obvious line 1]
- [Explain non-obvious line 2]

**Adapt for your use:**
- Change [X] to [your equivalent]
```

**Pattern Extraction (50-200 lines across files):**
```markdown
## [Pattern name]

Demonstrates: [what pattern solves]

### File structure needed:
[directory tree]

### Key file 1: [path]
[code]

### Key file 2: [path]
[code]

### How it connects:
[1-2 sentences on data flow]

### To adapt:
1. [First change]
2. [Second change]
```

---

## Context Matching Guide

### React Ecosystem

| Era | Patterns | Key Indicators |
|-----|----------|----------------|
| React 16-17 | Class components, HOCs, renderProps | `Component`, `componentDidMount` |
| React 18 | Concurrent features, Suspense, transitions | `startTransition`, `useDeferredValue` |
| React 19 | Server components default, use(), Actions | `"use server"`, `useActionState` |

### Next.js Versions

| Version | Router | Key Patterns |
|---------|--------|--------------|
| 12 and below | Pages Router | `pages/`, `getServerSideProps` |
| 13.0-13.3 | App Router (beta) | `app/` with limitations |
| 13.4+ | App Router (stable) | `app/`, server components |
| 14+ | Stable + improvements | `app/`, partial prerendering |
| 15 | Async request APIs | `await cookies()`, `await headers()` |

### Node.js Runtime

| Runtime | Module System | Indicators |
|---------|---------------|------------|
| Node CJS | require/module.exports | `"type": "commonjs"` or absent |
| Node ESM | import/export | `"type": "module"` |
| Bun | ESM native, Bun APIs | `Bun.serve`, `bun.lockb` |
| Deno | ESM, URL imports | `deps.ts`, `mod.ts` |

---

## Quality Signals Reference

Understanding what repo characteristics mean — for context, not filtering.

### Activity Signals

| Signal | What it might mean | Don't assume |
|--------|-------------------|--------------|
| **Last commit: this week** | Actively developed | Code is stable or good |
| **Last commit: months ago** | Stable or slow development | It's abandoned or broken |
| **Last commit: 2+ years** | Project is "done" or truly abandoned | The code doesn't work |

**Reality:** Some of the best learning code is in "finished" projects that haven't needed updates.

### Star Count Context

| Stars | Typical profile |
|-------|-----------------|
| **0-10** | Personal project, new project, niche solution |
| **10-100** | Useful to some people, might be exactly what you need |
| **100-1000** | Established solution, likely has docs |
| **1000-10000** | Popular tool/library, might be overkill for learning |
| **10000+** | Major project, probably a framework or tool itself |

**Hidden gems live in the 10-500 range.** Not famous enough to be over-engineered, popular enough to be validated.

### Describing Repos to Users

Instead of filtering, describe what you see:

- "Last updated 2021 — older but the auth pattern is still valid"
- "Smaller project (15 stars) but exactly solves the S3 upload case you asked about"
- "No test files — the code looks clean but you'd want to verify it works"
- "Full production setup (~80 files) — I can extract just the rate limiting middleware if you want simpler"

---

## Tool Integration

Works with:
- `mcp.grep.app` — Code search across millions of repos
- `gitmcp.io/docs` — Documentation for any GitHub repo
- GitHub MCP server — Repo search and metadata
- WebSearch — General web search for repos and examples

Without tools: Construct GitHub search URLs for user to explore.

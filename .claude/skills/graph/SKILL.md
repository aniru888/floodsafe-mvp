---
name: graph
description: Query the CodeGraphContext code graph for cross-cutting analysis (callers, callees, dead code, dependency chains)
argument-hint: "[callers <func>|calls <func>|dead-code|complexity|chain <from> <to>|tree <class>|deps <module>|find <pattern>|reindex|stats]"
user-invocable: true
allowed-tools: Bash, Read
---

# CodeGraphContext Graph Query

Query the CGC code graph for structural analysis that complements Serena's symbol-level intelligence.

## Prerequisites

- Neo4j Docker container must be running: `docker ps | grep cgc-neo4j`
- If not running: `docker start cgc-neo4j`
- CGC venv at `.venv-cgc/` with `codegraphcontext` installed

## CRITICAL: Command Prefix

The project `.env` overrides CGC config. ALL commands MUST use this prefix:

```bash
cd "C:/Users/Anirudh Mohan/Desktop/FloodSafe"
source .venv-cgc/Scripts/activate
PYTHONIOENCODING=utf-8 NEO4J_URI=bolt://localhost:7687 NEO4J_USERNAME=neo4j NEO4J_PASSWORD=floodsafe123 cgc -db neo4j <command>
```

## When to Use CGC vs Serena

| Need | Use | Why |
|------|-----|-----|
| Find symbol definition + body | **Serena** `find_symbol` | Precise, includes body |
| Find direct references to a symbol | **Serena** `find_referencing_symbols` | Language-server powered |
| Transitive call chains (N-hop) | **CGC** `analyze callers` / `analyze calls` | Graph traversal |
| Dead code detection | **CGC** `analyze dead-code` | Cross-language, whole-repo |
| Cyclomatic complexity report | **CGC** `analyze complexity` | Threshold-based filtering |
| Call chain between two symbols | **CGC** `analyze chain` | Graph shortest-path |
| Class inheritance tree | **CGC** `analyze tree` | Hierarchy visualization |
| Module dependencies | **CGC** `analyze deps` | Import-level relationships |
| Safe refactoring (rename/replace) | **Serena** editing tools | LSP-powered |
| Impact analysis before refactoring | **CGC then Serena** | CGC for scope, Serena for execution |

## Commands

Based on `$ARGUMENTS`, run the appropriate query:

### `callers <function_name>` — Who Calls This Function?

```bash
cgc -db neo4j analyze callers "$FUNCTION_NAME"
```

Shows the full call chain leading to a function. Useful for impact analysis before refactoring.

### `calls <function_name>` — What Does This Function Call? (Callees)

```bash
cgc -db neo4j analyze calls "$FUNCTION_NAME"
```

Shows everything a function depends on. Useful for understanding complexity and blast radius.

### `dead-code` — Unreferenced Symbols

```bash
cgc -db neo4j analyze dead-code
# Exclude FastAPI route decorators (they're entry points, not dead code):
cgc -db neo4j analyze dead-code --exclude route,router,get,post,put,delete,api
```

Finds unreferenced functions/classes. **Review before deleting** — some may be:
- FastAPI router entry points (decorated with `@router.get/post`)
- React components (imported in JSX)
- Event handlers (referenced in HTML/templates)

### `complexity` — Cyclomatic Complexity

```bash
cgc -db neo4j analyze complexity --threshold 10
```

Lists functions exceeding the complexity threshold. Candidates for refactoring.

### `chain <from> <to>` — Call Chain Between Two Symbols

```bash
cgc -db neo4j analyze chain "$SYMBOL_A" "$SYMBOL_B"
```

Finds the shortest call chain connecting two symbols. Useful for tracing data flow.

### `tree <class_name>` — Class Inheritance Hierarchy

```bash
cgc -db neo4j analyze tree "$CLASS_NAME"
```

Shows the inheritance hierarchy for a class.

### `deps <module_name>` — Module Dependencies

```bash
cgc -db neo4j analyze deps "$MODULE_NAME"
```

Shows imports and dependencies for a module.

### `find <pattern>` — Pattern Search in Graph

```bash
cgc -db neo4j find pattern "$PATTERN"
```

Search for symbols matching a pattern in the graph database. Returns up to 50 matches with type, location, and source.

### `reindex` — Re-index Codebase

```bash
cgc -db neo4j index apps/backend/src
cgc -db neo4j index apps/frontend/src
cgc -db neo4j index apps/ml-service/src
cgc -db neo4j index apps/iot-ingestion
```

NOTE: Root `cgc index .` doesn't work well due to `.cgcignore` exclusions. Index subdirectories explicitly.

### `stats` — Indexing Statistics

```bash
cgc -db neo4j stats
```

Shows files, functions, classes, modules, and repositories in the graph.

## Visualization

Add `--viz` or `-V` to any analyze/find command to generate an interactive HTML graph:

```bash
cgc -db neo4j analyze callers "FHICalculator" --viz
```

## Indexed Directories (as of 2026-03-08)

| Directory | Files | Content |
|-----------|-------|---------|
| `apps/backend/src` | ~120 | FastAPI routers, services, models |
| `apps/frontend/src` | ~180 | React components, hooks, contexts |
| `apps/ml-service/src` | ~60 | ML models, FHI calculator |
| `apps/iot-ingestion` | ~6 | IoT data ingestion |
| **Total** | **366 files, 2082 functions, 339 classes** | |

## Output

Present results as:
1. The call chain, dependency list, or analysis results
2. File paths for each node
3. Actionable insight (e.g., "safe to delete", "high fan-in — refactor carefully", "circular dependency detected")

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Database not configured" / fallback to FalkorDB | Ensure env vars are set: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` + `-db neo4j` flag |
| Neo4j container not running | `docker start cgc-neo4j` |
| Unicode/encoding errors | Ensure `PYTHONIOENCODING=utf-8` is set |
| "No indexed repos" / 0 files | Index subdirectories explicitly (see reindex section) |
| Stale results after refactor | Re-index affected directories |

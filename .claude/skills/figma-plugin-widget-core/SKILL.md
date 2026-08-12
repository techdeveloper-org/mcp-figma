---
name: figma-plugin-widget-core
description: "Provides complete engineering patterns for Figma plugin and widget development — sandbox isolation model, main-thread vs UI-thread constraints, message passing optimization, Figma scene graph traversal, widget state synchronization via useSyncedState, variable binding scope algebra, and plugin bundle optimization. Use when building Figma plugins, widgets, or Dev Mode extensions that interact with the Figma document tree, process design data programmatically, or sync state across collaborative sessions. Keywords: figma plugin development, figma widget api, figma plugin sandbox, figma scene graph traversal, figma usesyncedstate, figma plugin performance, figma postmessage optimization"
allowed-tools: Read,Glob,Grep,Bash,Edit,Write
user-invocable: true
---


<!-- generated-by: claude-global-library/tools/project_sync -->
<!-- source: skills/figma-plugin-widget-core/SKILL.md -- edit the library, then re-run sync_project.py -->

# figma-plugin-widget-core

## Description

Complete engineering patterns for Figma plugin and widget development. Covers the dual-context sandbox isolation model, main-thread vs UI-thread constraints and bridge patterns, scene graph traversal algorithms, widget state synchronization via useSyncedState, variable binding scope algebra, and plugin bundle optimization.

## 1. Plugin Architecture — Dual-Context Model

Figma plugins run in **two isolated contexts** that communicate via `postMessage()`.

**Context A — Main Thread (Sandbox):**
- Minimal JavaScript runtime — NOT a full browser environment
- Available: `figma.*` Plugin API, `Math`, `JSON`, `Array`, `Object`, `Promise`, `setTimeout` (limited)
- NOT available: `fetch`, `XMLHttpRequest`, DOM APIs (`document`, `window`), WebSockets, localStorage
- Has full read/write access to the Figma document scene graph
- Runs co-resident with Figma app in the same process (zero IPC overhead for scene graph access)

**Context B — UI Thread (iframe):**
- Full browser WebView environment (same as a web page)
- Available: `fetch`, XHR, DOM APIs, localStorage, WebSockets, Web Workers, Canvas
- NO direct scene graph access — cannot call `figma.*` APIs
- Runs as a cross-origin iframe (separate process per browser security policy)

**Communication bridge:** `postMessage()` with structured clone algorithm (see M2 for complexity). Data passing rules:
- Main thread → UI: `figma.ui.postMessage(data)`
- UI → Main thread: `window.parent.postMessage({ pluginMessage: data }, '*')` OR `parent.postMessage(...)` depending on API version

**Network access:** Controlled by `manifest.json` `networkAccess.allowedDomains` allowlist. Enforced at the Figma network layer (not just JavaScript). Even if UI iframe tries to `fetch` a non-listed domain, Figma's proxy intercepts and rejects the request.

**Capabilities field:**
- `"capabilities": ["inspect"]` → Dev Mode Plugins panel integration
- `"capabilities": ["codegen"]` → Code section in Inspect panel (generates code snippets)

## 2. Manifest.json Configuration

**manifest.json v2 required fields:**
```json
{
  "name": "My Plugin",
  "id": "1234567890",
  "api": "1.0.0",
  "main": "dist/main.js"
}
```

**Complete manifest with all optional fields:**
```json
{
  "name": "Design Token Sync",
  "id": "9876543210",
  "api": "1.0.0",
  "main": "dist/main.js",
  "ui": "dist/ui.html",
  "networkAccess": {
    "allowedDomains": [
      "https://api.github.com",
      "https://tokens.mycompany.com"
    ]
  },
  "capabilities": ["inspect", "codegen"],
  "permissions": ["currentuser", "activeusers"],
  "documentAccess": "dynamic-page",
  "widgetApi": 2
}
```

**Security rule:** Never use `"allowedDomains": ["*"]`. Always list specific required domains. Wildcard access bypasses Figma's security model.

**Widget manifest:** Requires `"widgetApi"` field with integer version. Widget entry point is a separate build target from plugin main thread.

## 3. Scene Graph Traversal and Node Operations

**Figma document hierarchy:**
```
DocumentNode
  └── PageNode[]
        └── SceneNode (FRAME, GROUP, COMPONENT, COMPONENT_SET, INSTANCE,
                       BOOLEAN_OPERATION, VECTOR, TEXT, RECTANGLE, ELLIPSE,
                       POLYGON, STAR, LINE, TABLE, STICKY, CONNECTOR,
                       WASHI_TAPE, SHAPE_WITH_TEXT)
```

**Key APIs:**
```typescript
figma.root                    // DocumentNode
figma.currentPage             // PageNode
node.children                 // SceneNode[] (if node has children)
node.parent                   // BaseNode | null
figma.root.findAll(callback)  // DFS, returns all matching nodes
figma.root.findAllWithCriteria({ types: ['FRAME', 'COMPONENT'] })  // type-filtered (faster)
```

**Iterative DFS (mandatory — recursive DFS risks call stack overflow on deep trees):**
```typescript
function iterativeDFS(root: BaseNode): SceneNode[] {
  const result: SceneNode[] = [];
  const stack: BaseNode[] = [root];
  while (stack.length > 0) {
    const node = stack.pop()!;
    if ('children' in node) {
      // Push children in reverse order to maintain left-to-right DFS order
      for (let i = node.children.length - 1; i >= 0; i--) {
        stack.push(node.children[i]);
      }
    }
    result.push(node as SceneNode);
  }
  return result;
}
```

**BFS (level-order traversal):**
```typescript
function bfs(root: BaseNode): SceneNode[] {
  const result: SceneNode[] = [];
  const queue: BaseNode[] = [root];
  while (queue.length > 0) {
    const node = queue.shift()!;
    result.push(node as SceneNode);
    if ('children' in node) queue.push(...node.children);
  }
  return result;
}
```

**Performance:** `findAllWithCriteria({types: [NodeType]})` is 2–5× faster than `findAll(predicate)` for type-filtering because the type check is a fast integer comparison vs a full callback function invocation.

## 4. Widget API — useSyncedState and State Persistence

**Widget state persistence:** Widget state is stored on the WidgetNode in Figma's document. It is synced via the same infrastructure as all Figma document changes (CRDT/OT-based). All users in a multiplayer session see the same widget state.

**useSyncedState API:**
```typescript
const [count, setCount] = useSyncedState<number>('count', 0);
const [config, setConfig] = useSyncedState<Config>('config', defaultConfig);
```

**Last-write-wins semantics:** Concurrent edits to the same useSyncedState key resolve by server timestamp or logical clock. Last writer wins. Design widget state schemas to be conflict-tolerant.

**Widget ID volatility on update:**
When a widget version is published (updated), Figma:
1. Deletes the old widget instance (old node ID lost)
2. Creates a new widget instance with a new node ID

`useWidgetId()` returns a different value after each widget update. **Never cache widget node IDs by reference.** Re-query after updates:
```typescript
const widgets = figma.currentPage.findAllWithCriteria({ types: ['WIDGET'] })
  .filter(w => w.widgetId === 'MY_REGISTERED_WIDGET_ID');
```

**State backwards compatibility — critical rules:**
1. **Adding new keys is safe** (if existing instances initialize from `defaultValue`)
2. **Never rename existing keys** — old instances lose that data silently
3. **Never remove existing keys** — removing drops data permanently from all existing instances
4. **Type changes break** — always migrate via a new key, not by reusing the old key name

**Plugin ↔ Widget state pre-configuration:**
```typescript
// From a Plugin (not Widget): set initial widget state before widget renders
const widget = figma.currentPage.findOne(n => n.type === 'WIDGET') as WidgetNode;
await widget.setWidgetSyncedState({ count: 42, label: 'initialized' });
```

## 5. Variables Binding Algebra and Mode Resolution

**VariableScope lattice (partial order of specificity):**
```
ALL_SCOPES
├── ALL_FILLS → FILL_COLOR
├── STROKE_COLOR
├── FONT_FAMILY, FONT_STYLE, FONT_WEIGHT, FONT_SIZE
├── LINE_HEIGHT, LETTER_SPACING, PARAGRAPH_SPACING, PARAGRAPH_INDENT
├── EFFECT_COLOR, EFFECT_FLOAT
├── OPACITY
├── WIDTH_HEIGHT, GAP
├── CORNER_RADIUS
└── GRID_STYLE
```

**Binding specificity precedence:**
Instance-level binding > Component-level binding > Frame-level binding (innermost binding wins).

**Mode resolution:**
```
resolve(variable, collection, activeMode) → typed_value
```
If collection has an extended collection:
```
value = extended_collection.value(variable, mode) ?? parent_collection.value(variable, mode)
```
(null-coalesce to parent collection's value if extended collection has no override for that mode/variable).

**Extended collection constraint:**
```
modes(extended_collection) ⊆ modes(parent_collection)
```
Extended collections cannot create new modes; they can only override values for parent-defined modes.

**Querying variable bindings from Plugin API:**
```typescript
const textNode = figma.currentPage.findOne(n => n.type === 'TEXT') as TextNode;
const bindings = textNode.boundVariables;
// bindings.fontSize?.id → variable ID bound to fontSize
// bindings.fills?.[0]?.color?.id → variable ID bound to first fill color
```

## 6. Plugin Performance and Bundle Optimization

**Main thread performance rules:**
- Never perform heavy computation synchronously — it blocks Figma's UI (all user interactions freeze)
- Chunk large scene graph traversals with progress reporting via `postMessage` every ~1000 nodes
- Prefer `findAllWithCriteria()` over `findAll()` for type-filtered searches

**Chunked traversal with UI progress:**
```typescript
async function traverseChunked(nodes: BaseNode[], chunkSize = 1000) {
  for (let i = 0; i < nodes.length; i += chunkSize) {
    const chunk = nodes.slice(i, i + chunkSize);
    processChunk(chunk);
    figma.ui.postMessage({ type: 'PROGRESS', done: i + chunkSize, total: nodes.length });
    // Yield to Figma's event loop between chunks
    await new Promise(r => setTimeout(r, 0));
  }
}
```

**Bundle optimization:**
- Use ES module syntax (`import`/`export`) — enables tree-shaking in esbuild/webpack/rollup
- CommonJS (`require()`) blocks static analysis → no tree-shaking → larger bundle
- Main thread: single file (no code splitting supported)
- UI iframe: supports dynamic `import()` (code splitting available)
- Target: <5MB raw, <2MB gzipped for plugin bundle

**clientStorage limits:** [UNVERIFIED — community reports only: ~1MB per key, ~5MB total; not officially documented by Figma.] Use for persisting user preferences only, not large design data. Fallback: use external storage via UI iframe fetch.

**Security rule for credentials:** Never store Figma tokens, OAuth credentials, or PATs in `figma.clientStorage` — clientStorage is accessible by any plugin code running in the user's Figma environment. Use OS keychain, environment variables, or secure server-side storage.

## Deep Mathematical Foundations

### M1: Plugin Sandbox Isolation Math (Memory Quota + GC Modeling)

**Process model:**
- Plugin main thread: co-resident with Figma app in same process → zero IPC overhead for scene graph access. Scene graph nodes accessed via direct JavaScript object references (proxies/descriptors — actual data is NOT copied into plugin heap until explicitly read)
- UI iframe: cross-origin iframe (separate process per browser policy) → `postMessage()` overhead = structured clone cost + OS IPC queue latency

**Memory quota:** Figma does not publish hard memory limits for the plugin sandbox. Community-observed soft limit ≈ 50MB for plugin main thread heap [UNVERIFIED — community reports only]. Plugin main thread shares the V8 heap with the Figma runtime.

**V8 GC pause estimation:**
```
t_gc ≈ live_heap_bytes / GC_throughput
GC_throughput ≈ 100–500 MB/s for V8 major GC
```
For heap < 100MB: incremental GC pause < 16ms (< 1 frame at 60fps). Above 100MB: major GC pauses scale as O(live_heap_bytes) — can exceed one frame and cause visible Figma UI jank.

**Memory model detail:** Plugin API node property access returns proxies/descriptors. Heap allocation occurs only for data explicitly created in plugin JavaScript (arrays, objects built from node property reads). A plugin that reads `node.name` only allocates a string, not the full node data structure.

**Sandbox isolation guarantees:**
- Plugin cannot access other tabs' data or other plugins' memory
- Each plugin has an isolated JavaScript execution context
- Crash in plugin JavaScript does not crash the Figma app (exception boundary at sandbox entry)

**Network isolation:**
`allowedDomains: ["none"]` blocks ALL network from both contexts. Non-listed domains in the allowlist are blocked at Figma's network proxy layer, not at the JavaScript API level. This interception occurs even if the UI iframe calls `fetch()` directly.

### M2: Message Passing Complexity (Structured Clone Algorithm)

**Structured Clone Algorithm (HTML Living Standard §2.7) supported types:**
- Primitives: `null`, `undefined`, `boolean`, `number`, `string`, `bigint`
- Wrapper objects: `Boolean`, `String`, `Number`
- Dates, RegExp, Blob, File, ArrayBuffer, TypedArray, ImageData
- Collections: `Array`, plain `Object`, `Map`, `Set`, `Error`
- **NOT supported:** `Function`, `Symbol`, DOM nodes, `WeakMap`, `WeakRef`, `Proxy`, class instances with methods

**Clone complexity:**
```
O(N_nodes)
```
Where N_nodes = total nodes in the object graph (not bytes). For a flat object with k properties: O(k). For a tree of depth d and branching factor b: O(b^d).

**Total message latency:**
```
t_total = α × N_nodes (serialize) + t_queue + β × N_nodes (deserialize)
```
Typical values: α ≈ β ≈ 0.1μs/node; t_queue ≈ 0.1–1ms for same-machine `postMessage`.

**Transferable objects (zero-copy transfer):**
```javascript
// Transfer ArrayBuffer ownership — O(1), buffer neutered in sender
figma.ui.postMessage(data, [arrayBuffer]);
```
Use for large binary payloads (image data, audio buffers). Buffer is "neutered" (inaccessible) in the sender after transfer.

**JSON vs structured clone:** For simple flat objects without special types, `JSON.stringify` + `JSON.parse` can be faster than structured clone due to highly optimized string paths in V8. Benchmark with actual payload before optimizing.

**Chunking strategy for large payloads:**
For payloads > 10KB of non-transferable data: split into chunks of ≤10KB each. Send with chunk index + total count for reassembly. Prevents single large clone from blocking the message queue.

**Max throughput:** Bounded by main thread event loop utilization. If main thread is traversing 10,000 nodes (≈10ms at 1μs/node), all incoming messages queue for ≈10ms during traversal.

### M3: Node Traversal Algorithms (DFS/BFS + Complexity)

**Document tree properties:**
- V = all nodes, E = parent-child edges
- Tree graph: |E| = |V| − 1 (every node except root has exactly one parent)
- Total traversal: O(V)

**Iterative DFS (mandatory for large documents):**
```
stack = [root]
while stack not empty:
    node = stack.pop()
    process(node)
    push children in reverse order  // maintain left-to-right order
```
Space complexity: O(max_depth). Figma practical depth: 5–20 for typical designs, up to 100 in deeply nested component libraries.

**Recursive DFS — NEVER USE IN PRODUCTION:**
```
function dfs(node):
    process(node)
    for child in node.children: dfs(child)  // UNSAFE — stack overflow at depth ~10,000
```
JavaScript default call stack: ~10,000–15,000 frames. Deep Figma documents WILL overflow.

**BFS (level-order traversal):**
```
queue = [root]
while queue not empty:
    node = dequeue()
    process(node)
    enqueue all children
```
Space complexity: O(max_width). Figma max width (siblings per level) can be very large in component library frames.

**Built-in API complexity:**
- `findAll(cb)`: O(V) DFS; builds full result array in memory. For V > 100,000 nodes: prefer chunked traversal.
- `findAllWithCriteria({types:[T]})`: O(V) worst case, but type check is an integer comparison (2–5× faster per node than callback invocation).

**Visited set DFS (for subgraph traversal):**
```
visited = new Set<string>()  // set of node IDs
function traverseSubgraph(node):
    if visited.has(node.id): return
    visited.add(node.id)
    process(node)
    for child in node.children: traverseSubgraph(child)
```
O(V) time, O(V) space. Use when processing subgraphs that may share nodes (e.g., after resolving instances).

### M4: Widget State Sync Math (CRDT Vector Clocks + Convergence)

**State storage model:** Widget state persisted as key-value pairs on the WidgetNode in Figma's document. Propagated via Figma's internal document sync protocol (OT/CRDT-based; exact internal architecture not publicly documented by Figma).

**Last-write-wins semantics (per key):** Concurrent edits to the same key are resolved by server-assigned total ordering (likely wall-clock timestamp + logical clock as tiebreaker).

**Vector clock conceptual model:**
- Each client i maintains logical clock V_i
- State update = (key, value, V_i++) sent to server
- Conflict resolution: if updates V_a and V_b are concurrent (incomparable vector clocks → neither "happened before" the other), server applies a total order (timestamp tiebreaker)

**Convergence bound:**
All clients converge to identical state after all messages delivered. Delivery latency:
```
δ_sync ≈ RTT_to_figma_server + broadcast_fanout_time
```
For n editors: O(n) server-side broadcast. Typical δ_sync = 50–300ms.

**Widget ID volatility formula:**
```
After update: new_node.id ≠ old_node.id
Query pattern:
  figma.currentPage
    .findAllWithCriteria({types: ['WIDGET']})
    .filter(w => w.widgetId === 'MY_MANIFEST_WIDGET_ID')
```
`widgetId` = the `id` field from widget manifest (stable across version updates). `node.id` = ephemeral Figma-assigned ID (changes on each widget update).

**Backwards compatibility algebra:**
- ADD new key with defaultValue: safe iff `defaultValue` is a valid state for all existing instances during the migration window
- REMOVE key: breaks existing instances that expect the key; never remove (use migration pattern instead)
- RENAME key: equivalent to simultaneous REMOVE + ADD; never rename (migrate via new key)
- TYPE CHANGE: breaks deserialization in existing instances; never change type of existing key

### M5: Variable Binding Algebra (Scope Lattice + Mode Resolution)

**VariableScope lattice:**
```
ALL_SCOPES ⊇ ALL_FILLS ⊇ {FILL_COLOR}
ALL_SCOPES ⊇ STROKE_COLOR
ALL_SCOPES ⊇ FONT_SIZE, FONT_FAMILY, FONT_STYLE, FONT_WEIGHT
ALL_SCOPES ⊇ LINE_HEIGHT, LETTER_SPACING, PARAGRAPH_SPACING, PARAGRAPH_INDENT
ALL_SCOPES ⊇ CORNER_RADIUS
ALL_SCOPES ⊇ EFFECT_COLOR, EFFECT_FLOAT
ALL_SCOPES ⊇ OPACITY
ALL_SCOPES ⊇ WIDTH_HEIGHT, GAP
ALL_SCOPES ⊇ GRID_STYLE
```

**Binding specificity precedence (innermost wins):**
```
instance-level binding > component-level binding > frame-level binding
```

**Mode resolution:**
```
resolve(variable, collection, activeMode) → typed_value
```
Algorithm:
1. Look up activeMode in collection's modes
2. If variable has a value override for activeMode: return that value
3. If collection is an extended collection: look up parent collection's value for same variable + mode
4. Parent collection's value takes effect if extended collection has no override

**Extended collection constraint:**
```
modes(extended_collection) ⊆ modes(parent_collection)
```
Extended collections can only override values for parent-defined modes. They cannot create new modes. Mode deletion in extended collection: the override is deleted, but the parent mode and its value persist.

**Temporary ID algebraic properties:**
Let φ: TempID → RealID be the temp ID resolution function applied to all CREATE operations in a POST body.
- φ is injective (one-to-one): each temp ID maps to a unique real ID
- φ is surjective onto newly created real IDs
- All forward references within the request body are resolved by φ before storage — enabling CREATE order within the body to be topological rather than requiring pre-creation

**Mode propagation scope:**
Setting mode on a frame propagates resolution to all descendant nodes with variables bound to variables in that collection. Propagation cost: O(subtree_size) in Plugin API.

### M6: Plugin Bundle Size Math (Tree-Shaking + Gzip Entropy)

**Tree-shaking reachability:**
- Requires ES module syntax (`import`/`export`) — enables static call graph analysis
- CommonJS (`require()`) is dynamic: cannot determine reachable set statically → no tree-shaking
- Reachable set R = transitive closure from entry points (plugin `main()` + `figma.ui.show()`)
- Unreachable set U = S_total \ R
- Bundle size after tree-shaking: `|R|` bytes

**Tree-shaking effectiveness:**
```
ratio = (S_total − |R|) / S_total
```
Typical for well-structured ESM libraries: 30–60% size reduction.

**Shannon entropy lower bound (information theory):**
```
H(source) = −Σ p(symbol) × log₂(p(symbol))
```
For JavaScript source (highly structured text): ~4–5 bits/byte. No lossless compressor can achieve compression ratio below H(source)/8. This sets a theoretical floor on bundle size.

**Compression cascade:**
```
S_original
  → minify (rename vars, remove whitespace): S_min ≈ 0.75 × S_original
  → tree-shake (remove dead code): S_shake ≈ 0.50 × S_min
  → gzip (LZ77 + Huffman): S_gzip ≈ 0.35 × S_shake
Total: S_final ≈ 0.35 × 0.50 × 0.75 × S_original ≈ 0.13 × S_original (87% total reduction)
```

**Target bundle sizes:**
- Main thread bundle: <5MB raw, <2MB gzipped (single file, no code splitting)
- UI iframe bundle: <5MB raw, supports dynamic `import()` code splitting

**gzip vs Brotli:**
- gzip: compression ratio ≈ 0.35 for typical JS
- Brotli: compression ratio ≈ 0.30 (slightly better, larger dictionary)
- Figma plugin distribution uses Figma's CDN; actual compression method per Figma's delivery infrastructure

## Anti-Patterns to Avoid

- **Calling `fetch()` or accessing `document`/`window` from the main-thread sandbox**: §1 is explicit that Context A is not a full browser environment — network and DOM APIs exist only in the UI iframe (Context B); code that assumes `fetch` is available anywhere in the plugin fails at runtime specifically on the main thread, not universally, which makes the bug easy to miss in an environment where the developer only tested UI-thread code paths.
- **Using `"allowedDomains": ["*"]` for convenience during development and shipping it**: §2's security rule states this bypasses Figma's network security model entirely — a wildcard allowlist means the UI iframe can `fetch` any domain, defeating the purpose of `networkAccess` as a containment boundary rather than just a convenience config.
- **Using recursive DFS on the scene graph instead of the iterative form**: §3 flags this as mandatory, not stylistic — a sufficiently deep or wide Figma document (nested frames, large component trees) can overflow the call stack with a naive recursive traversal, and this failure mode only appears on large real-world files, not the small test files a plugin is typically developed against.
- **Caching a widget's node ID by reference across a widget version update**: §4 states Figma deletes the old widget instance and creates a new one with a new node ID on every published update — code that stores a `useWidgetId()` value once and reuses it later silently operates on a stale/nonexistent reference after the next widget publish, rather than failing loudly.
- **Renaming or removing a `useSyncedState` key during a widget update**: §4's backwards-compatibility rules are asymmetric — adding new keys is safe, but renaming or removing an existing key silently drops that data from every existing widget instance in every document that has already synced state, with no migration path back.
- **Overriding a variable value in an extended collection for a mode the parent collection doesn't define**: §5's constraint `modes(extended_collection) ⊆ modes(parent_collection)` means extended collections can only override parent-defined modes, never introduce new ones — attempting to bind a value for a mode that doesn't exist on the parent collection violates the lattice structure the mode-resolution algorithm depends on.
- **Running a heavy synchronous scene-graph operation on the main thread without chunking**: §6 notes this blocks Figma's entire UI (all user interactions freeze) — processing a large `findAll()` result set in one synchronous pass, rather than chunking with `postMessage` progress updates and yielding via `setTimeout(r, 0)` between chunks, turns a large-file operation into an apparent Figma hang rather than a visible progress bar.
- **Storing Figma tokens, OAuth credentials, or PATs in `figma.clientStorage`**: §6's security rule states clientStorage is accessible by any plugin code running in the user's Figma environment — this is not a size or reliability concern but a credential-exposure one, since any other installed plugin (malicious or compromised) can read clientStorage values a well-behaved plugin wrote there.

## India-Specific Layer

**DPDP Act 2023 §4 (Lawful Processing):**
If a plugin processes design files containing PII (user photos in mockups, real names in UI prototypes), the plugin operator is a data fiduciary under DPDP Act 2023. A lawful basis (§4 — consent or legitimate purpose) must exist before the plugin processes such data. PII processing via plugin UI thread (clientStorage, fetch to external server) requires explicit consent or legitimate purpose documentation.

**DPDP Act 2023 §8 (Data Fiduciary Obligations):**
Plugins distributed to Indian users must implement:
- **Purpose limitation:** plugin must not use design data for purposes beyond its stated function
- **Data minimization:** collect only data necessary for the plugin's function
- **Storage limitation:** delete data when no longer needed
- **Security safeguards:** encrypt any PII in transit or at rest
- **Accuracy maintenance:** not applicable to read-only plugins

**DPDP Act 2023 §3(c) (Data Processor):**
A plugin acting on behalf of a design agency (data fiduciary) is a data processor under §3(c). The plugin must not process design data beyond the fiduciary's instructions. Sub-processing (sending data to third-party APIs from plugin UI iframe) requires an explicit data processing agreement.

**IT Act 2000 §66C (Identity Theft):**
Plugins must not store or transmit Figma credentials (PAT, OAuth tokens) in plaintext in plugin code, `clientStorage`, manifest, or any client-accessible location. Exposure of credentials in client-side code constitutes identity theft under §66C. Use OS keychain, environment variables, or secure server-side credential storage.

**IT Act 2000 §43A (Reasonable Security Practices):**
Plugins handling sensitive design assets (financial UI mockups with account numbers, medical app prototypes with patient data) must implement reasonable security practices per IT (Reasonable Security Practices) Rules 2011. Minimum: HTTPS for all network requests, no logging of sensitive data, encryption of persisted data.

## Response Rules

- Always use iterative (not recursive) DFS for scene graph traversal — recursive DFS risks call stack overflow on deeply nested Figma documents (depth > 10,000 nodes can exhaust the JavaScript call stack).
- Always make network requests from the UI iframe (browser context), never from the main thread — `fetch` is unavailable in the main thread. Network calls must go through the postMessage bridge.
- Always implement backwards-compatible widget state schema changes — never rename or remove existing useSyncedState keys from published widgets. Only add new keys with safe default values.
- Always validate the manifest.json domain allowlist before attempting `fetch` in UI iframe — requests to non-listed domains are silently blocked at the Figma network proxy layer (no JavaScript error is thrown).
- Always use `hmac.compare_digest()` or equivalent timing-safe comparison for any HMAC or secret verification performed within plugin code. Never use `===` for secret comparison.

## What Not to Do

- Do not use recursive tree traversal for Figma documents — deep nesting causes call stack overflow at depths > ~10,000. Always use iterative DFS with an explicit stack array.
- Do not perform heavy computation (large sort operations, complex analysis of 10,000+ nodes) synchronously in the main thread — it freezes Figma's UI for all users. Chunk work with progress reporting.
- Do not cache widget node IDs by reference across widget version updates — Figma creates a new node ID on each widget version publish. Always re-query widgets by their `widgetId` property from the manifest.
- Do not store Figma tokens, OAuth credentials, or PATs in `figma.clientStorage` — clientStorage is accessible by any plugin code executing in the user's Figma environment and is not a secure credential store.
- Do not set `networkAccess.allowedDomains: ["*"]` — wildcard access bypasses Figma's network security model. Always list specific required domains.

## Output Expectations

Responses provide:
- Dual-context architecture diagram and constraint table (main thread vs UI iframe)
- Complete manifest.json configuration templates with all optional fields
- Iterative DFS and BFS scene graph traversal code with chunking
- postMessage bridge patterns including chunking for large payloads and Transferable usage
- useSyncedState schema design guidelines with backwards-compatibility rules
- Variable binding query code with scope and mode resolution examples
- Bundle optimization configuration (esbuild/webpack/rollup for ESM + tree-shaking)
- M1–M6 full mathematical derivations with all formulas and proofs
- DPDP Act 2023 compliance checklist for plugin distribution in India

## Skill Scope

**In scope:** Plugin API (main thread constraints, scene graph traversal, clientStorage), Widget API (useSyncedState lifecycle, backwards compatibility, widget ID volatility), manifest.json configuration, postMessage bridge patterns with structured clone constraints, bundle optimization (tree-shaking, gzip), variable binding scope lattice and mode resolution from Plugin API context.

**Out of scope:** REST API authentication and rate limiting (see figma-rest-api-core), design token pipeline (see design-tokens-automation-core), CI/CD pipeline orchestration (see figma-ci-cd-pipeline-core), code generation algorithms (see figma-codegen-core), AI-powered automation quality scoring (see figma-ai-automation-core), multi-platform token deployment (see figma-multiplatform-tokens-core).

## Version: 1.1 — Added Anti-Patterns to Avoid section (main-thread API misuse, wildcard networkAccess, recursive DFS stack overflow risk, stale widget ID caching, useSyncedState key rename/removal, extended-collection mode violation, unchunked main-thread blocking, clientStorage credential exposure)

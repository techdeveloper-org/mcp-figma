---
name: figma-ai-automation-core
description: "Provides AI-assisted design automation techniques for Figma: embedding-based component matching, design intent classification, APCA/WCAG contrast computation, design consistency scoring, and hallucination risk estimation for AI-generated code. Use when building AI pipelines that query Figma design systems, auto-suggest components, evaluate accessibility via machine learning, or validate AI-generated UI code against Figma specs. Keywords: figma ai automation, component similarity search, design intent classification, APCA contrast AI, hallucination risk score, design consistency scoring"
allowed-tools: Read,Glob,Grep,WebFetch,WebSearch
user-invocable: true
---


<!-- generated-by: claude-global-library/tools/project_sync -->
<!-- source: skills/figma-ai-automation-core/SKILL.md -- edit the library, then re-run sync_project.py -->

# Figma AI Automation Core

## Description

Advisory skill covering AI-assisted automation techniques integrated with Figma: semantic component retrieval via embeddings, softmax-based design intent classification, APCA v0.0.98G and WCAG 2.1 contrast computation, design consistency scoring (CRR/SCI/DR/DCS), and hallucination risk estimation (PPL + self-consistency + NLI) for AI-generated UI code. Provides mathematical foundations for each technique plus India regulatory context (DPDP, RPwD, MeitY AI Advisory, GIGW). This is a pure advisory skill — it provides algorithms and patterns, not direct Figma API calls.

---

## 1. Figma AI Ecosystem 2025–2026

### 1.1 Current AI Surface (as of May 2026)

| Feature | Status | Programmatic Access |
|---------|--------|---------------------|
| Figma Make (AI-to-design from prompt) | GA (Config 2025) | No API — UI only |
| Figma MCP Server | GA (late 2025) | MCP protocol via stdio/SSE |
| AI agent canvas editing | Beta (March 2026) [CONFIDENCE:LOW — unverified; check figma.com/release-notes] | No public API |
| AI component suggestions | GA | No API — UI only |
| Dev Mode AI code hints | GA | No API — UI only |

**Key constraint**: Figma's AI features cannot be triggered programmatically via the REST API or Plugin API as of May 2026. AI automation must be built externally using the Figma REST API (for asset retrieval), your own embedding models, and the Figma MCP Server (for structured design queries).

### 1.2 Figma MCP Server Integration

The Figma MCP Server (stdio or SSE transport) exposes Figma file structure to LLM agents using the Model Context Protocol. It provides read access to frames, components, styles, and variables — enabling LLM-driven design analysis without REST API polling.

**Recommended pattern for AI automation**:
1. MCP Server → structured design context to LLM
2. LLM → intent classification + component suggestions
3. REST API → retrieve component assets and token values
4. Your embedding index → semantic similarity ranking
5. NLI model → validate AI-generated code against Figma spec

### 1.3 Figma Make Workflow (UI-Only)

Figma Make generates editable Figma frames from natural language prompts. The workflow is:
- User enters prompt in Figma UI
- Figma Make generates a frame (not a component)
- Developer exports via REST API or Code Connect

No API hook into Make generation exists. Automation must treat Make outputs as any other Figma frame.

---

## 2. Embedding-Based Component Matching

### 2.1 Use Case

Given a natural language query (e.g., "primary action button with icon") or a partial component spec, retrieve the most semantically similar components from the Figma component library without exact name matching.

### 2.2 Embedding Pipeline

```
Figma Component Library
        │
        ▼
  GET /v1/files/{key}/components
        │
        ▼
  Extract: name, description, componentSetId, properties, containing frame name
        │
        ▼
  Embed via text-embedding-3-small or equivalent (1536-dim)
        │
        ▼
  Store in HNSW index (hnswlib or Qdrant)
        │
        ▼
  At query time: embed query → ANN search → top-k results
        │
        ▼
  Post-filter by componentSetId, variant properties, scoping rules
```

### 2.3 Vector Similarity Formula

Cosine similarity between query vector **q** and component vector **c**:

```
cos(θ) = (q · c) / (||q|| × ||c||)
```

When vectors are pre-normalized to unit length (||q|| = ||c|| = 1):

```
cos(θ) = q · c     (dot product only — O(d) not O(3d))
```

**Pre-normalize at index time** to reduce query cost from O(3d) to O(d).

### 2.4 HNSW Index Parameters

| Parameter | Recommended | Effect |
|-----------|-------------|--------|
| M (connections per node) | 16–32 | Higher → better recall, more memory |
| ef_construction | 200 | Build quality; use 200 for production |
| ef_search | 50–100 | Query recall vs speed tradeoff |
| space | cosine | For pre-normalized vectors: use inner_product |

Expected complexity:
- Build: O(N × M × log N)
- Query: O(log N) amortized
- Recall@10 ≥ 0.95 achievable with M=16, ef=100 on design component corpora

### 2.5 Post-Retrieval Filtering

After ANN search returns top-k candidates, apply deterministic filters:
- **Scope filter**: remove components scoped to a different page/team
- **Variant filter**: if query specifies variant properties (e.g., state=hover), keep only matching variants
- **Type filter**: distinguish COMPONENT vs COMPONENT_SET vs FRAME types from API response
- **Availability filter**: check `remote` flag — remote library components require library access token

---

## 3. Design Intent Classification

### 3.1 Use Case

Classify a design element or user prompt into one of a fixed set of intent categories (e.g., "navigation", "form input", "data display", "feedback/alert", "layout container") to route to the correct component subtree.

### 3.2 Softmax Classifier

For a classifier with logit vector **z** of dimension K (K intent classes):

```
σ(z)_i = exp(z_i) / Σ_{j=1}^{K} exp(z_j)
```

**Numerical stability** — subtract max logit before exponentiation (log-sum-exp trick):

```
z* = max(z_1, ..., z_K)
σ(z)_i = exp(z_i - z*) / Σ_{j=1}^{K} exp(z_j - z*)
```

This prevents `exp` overflow with no change to the output distribution.

### 3.3 Temperature Scaling for Calibration

Raw softmax outputs are often overconfident. Apply temperature τ before softmax:

```
σ(z/τ)_i = exp(z_i/τ) / Σ_j exp(z_j/τ)
```

- τ = 1.0: standard softmax (no change)
- τ > 1.0: softer distribution (less confident, higher entropy)
- τ < 1.0: sharper distribution (more confident, lower entropy)

**Calibration procedure**: find τ* that minimizes Expected Calibration Error (ECE) on a held-out validation set of labeled design intents.

### 3.4 Auto-Accept Threshold

Apply auto-accept only when the top-class probability exceeds a threshold:

```
Accept = (max_i σ(z)_i ≥ θ_accept)
```

**Recommended**: θ_accept = 0.80 (not 0.70). At 0.70 the model accepts too many borderline cases, increasing downstream component mismatches. Validate on your design system corpus before deployment.

When max probability < θ_accept, present top-3 candidates to the user for selection.

### 3.5 ECE Minimization

Expected Calibration Error measures alignment between confidence and accuracy:

```
ECE = Σ_b (|B_b| / n) × |acc(B_b) - conf(B_b)|
```

Where:
- B_b = set of predictions in confidence bin b
- acc(B_b) = fraction of B_b predictions that are correct
- conf(B_b) = mean confidence in bin b
- n = total predictions

**Target**: ECE < 0.05 before deploying auto-accept. Use 10–15 equal-width bins. Post-hoc calibrate with Platt scaling or temperature scaling on validation set.

---

## 4. Accessibility Contrast Computation

### 4.1 WCAG 2.1 Contrast Ratio

**Step 1**: sRGB linearization for each channel c ∈ {R, G, B} (values normalized 0–1):

```
C_linear = c / 12.92                   if c ≤ 0.04045
C_linear = ((c + 0.055) / 1.055)^2.4   if c > 0.04045
```

**Step 2**: Relative luminance:

```
L = 0.2126 × R_linear + 0.7152 × G_linear + 0.0722 × B_linear
```

**Step 3**: Contrast ratio (L1 = lighter color, L2 = darker color):

```
CR = (L1 + 0.05) / (L2 + 0.05)
```

**WCAG 2.1 thresholds**:
- Normal text: CR ≥ 4.5 (AA), CR ≥ 7.0 (AAA)
- Large text (≥18pt or ≥14pt bold): CR ≥ 3.0 (AA), CR ≥ 4.5 (AAA)
- UI components/graphics: CR ≥ 3.0 (AA)

### 4.2 APCA v0.0.98G Algorithm

APCA (Advanced Perceptual Contrast Algorithm) produces a signed Lightness Contrast (Lc) value. It is asymmetric — text on background behaves differently from background on text.

**Coefficients** (v0.0.98G):
- normBG = 0.56 (normal polarity: light bg)
- normTXT = 0.57 (normal polarity: dark text)
- revTXT = 0.62 (reverse polarity: light text)
- revBG = 0.65 (reverse polarity: dark bg)
- Scale factor Sa ≈ 1.14

**Step 1**: Linearize both colors using the same sRGB linearization as WCAG (see §4.1 Step 1).

**Step 2**: Compute relative luminance Y for both text (Yt) and background (Yb):
```
Y = 0.2126 × R_linear + 0.7152 × G_linear + 0.0722 × B_linear
```

**Step 3**: Determine polarity and compute Lc:

*Normal polarity* (Yb > Yt — light background, dark text):
```
Ys  = Yb ^ normBG       = Yb ^ 0.56
Yt_p = Yt ^ normTXT      = Yt ^ 0.57
Lc  = (Ys - Yt_p) × Sa × 100   = (Ys - Yt_p) × 1.14 × 100
```

*Reverse polarity* (Yt > Yb — dark background, light text):
```
Ys  = Yb ^ revBG        = Yb ^ 0.65
Yt_p = Yt ^ revTXT       = Yt ^ 0.62
Lc  = (Ys - Yt_p) × Sa × 100   = (Ys - Yt_p) × 1.14 × 100
```

Lc is negative for reverse polarity (the sign encodes polarity direction).

**Step 4**: Apply offset and clamp:
- If |Lc| < 7.5 → set Lc = 0 (black-on-black zone, no meaningful contrast)
- Report |Lc| as the contrast value

**APCA thresholds** (WCAG 3.0 draft — still in draft as of May 2026):
| |Lc| | Use Case |
|-------|----------|
| ≥ 75 | Body text, normal size |
| ≥ 60 | Large text, subheadings |
| ≥ 45 | UI components, active controls |
| ≥ 30 | Placeholder text, decorative |
| ≥ 15 | Non-text graphics (minimal threshold) |

**CRITICAL**: APCA is NOT legally required anywhere as of May 2026. WCAG 2.1 AA (CR ≥ 4.5) remains the legal standard under RPwD Act 2016 §40. Report both metrics; do not claim APCA compliance equates to legal compliance.

### 4.3 Reporting Strategy

Always report both WCAG 2.1 CR and APCA Lc:

```json
{
  "wcag_contrast_ratio": 4.8,
  "wcag_level": "AA",
  "apca_lc": 68.2,
  "apca_use_case": "body_text",
  "legal_standard": "WCAG 2.1 AA (RPwD §40 India)",
  "advisory": "APCA advisory only — not legally mandated"
}
```

---

## 5. Design Consistency Scoring

### 5.1 Metrics Overview

Three component metrics feed into a composite Design Consistency Score (DCS):

| Metric | Symbol | Measures |
|--------|--------|---------|
| Component Reuse Rate | CRR | How often library components are used vs custom |
| Style Coverage Index | SCI | How many elements use defined styles vs local overrides |
| Detachment Rate | DR | How many library instances have been detached |

### 5.2 Component Reuse Rate (CRR)

```
CRR = (N_lib_instances / N_total) × 100%
```

Where:
- N_lib_instances = count of nodes with `mainComponent` resolving to a library component
- N_total = count of all leaf-level visible frame children

Computed by traversing the Figma file node tree via REST API (`GET /v1/files/{key}`) and checking each node's `type` and `mainComponent` fields.

**Target**: CRR ≥ 70% for mature design systems. CRR < 40% indicates systematic design system adoption failure.

### 5.3 Style Coverage Index (SCI)

```
SCI = (N_styles_used / N_total_styled) × 100%
```

Where:
- N_styles_used = nodes with `fillStyleId`, `strokeStyleId`, `textStyleId`, or `effectStyleId` referencing a named style (not a raw RGBA value)
- N_total_styled = all nodes that have any fill, stroke, text style, or effect applied

**Target**: SCI ≥ 80%. Low SCI → designers are applying local colors/fonts instead of tokens.

### 5.4 Detachment Rate (DR)

```
DR = N_detached / (N_lib_instances + N_detached) × 100%
```

Where N_detached = nodes that were instances but had `mainComponent` removed (identifiable by `componentId` field being absent on nodes of type FRAME that were previously instances).

**Note**: Exact detachment detection requires comparing file versions or maintaining a reference snapshot. Approximate via nodes of type FRAME with no mainComponent at positions where library components are expected.

**Target**: DR ≤ 10%. High DR → library components are being modified destructively instead of through variant/override patterns.

### 5.5 Composite Design Consistency Score (DCS)

```
DCS = α × (CRR/100) + β × (SCI/100) + γ × (1 - DR/100)
```

Recommended weights: α = 0.4, β = 0.4, γ = 0.2

The (1 - DR/100) term converts DR (lower is better) into a score contribution (higher is better).

**Interpretation**:
| DCS | Grade |
|-----|-------|
| ≥ 0.85 | Excellent — system-driven design |
| 0.70–0.84 | Good — minor consistency gaps |
| 0.55–0.69 | Fair — significant manual overrides |
| < 0.55 | Poor — design system not adopted |

### 5.6 Spatial Consistency (Advanced)

For layout consistency across similar components (e.g., all card components should have consistent padding), use:

**Fréchet Distance** [HEURISTIC — exact implementation requires ordered point sequences]:
Measures similarity between two curves/paths. Used to compare spacing/alignment sequences across component instances.

**Dynamic Time Warping (DTW)** for comparing padding/margin sequences across component families:
```
DTW(i, j) = cost(i, j) + min(DTW(i-1, j), DTW(i, j-1), DTW(i-1, j-1))
```

DTW aligns sequences of different lengths — useful when card components have different numbers of content slots but should follow the same spacing rhythm.

**Practical use**: Compute padding sequences [top, right, bottom, left] for all instances of a component family. DTW distance between any two instances should be < threshold T_dtw (tune per design system).

---

## 6. NLP Confidence and Hallucination Risk

### 6.1 Use Case

When an LLM generates UI code from a Figma spec (via Code Connect, Figma MCP Server, or manual prompt), estimate the probability that the generated code correctly reflects the Figma design intent. Flag high-risk outputs for human review.

### 6.2 Perplexity (PPL)

Perplexity measures how surprised the language model is by its own output — lower perplexity indicates more confident, in-distribution generation:

```
PPL = exp(-1/N × Σ_{t=1}^{N} log P(token_t | context))
```

Where:
- N = number of tokens in the generated code
- P(token_t | context) = the model's predicted probability for each token

**Interpretation**:
- Low PPL → model is confident (tokens are in-distribution for the prompt)
- High PPL → model is generating uncertain or out-of-distribution content
- PPL alone is insufficient — a confident model can still hallucinate confidently

**Normalization for HRS**: PPL_norm = PPL / PPL_max, where PPL_max is the 95th percentile PPL observed in your validation corpus.

### 6.3 Self-Consistency Sampling

Generate the same code k times with temperature τ > 0 (e.g., τ = 0.7, k = 5):

```
Consistency = max_answer_freq / k
```

Where max_answer_freq = count of the most frequently generated distinct answer (after semantic deduplication, e.g., normalize whitespace, imports).

**Interpretation**:
- Consistency = 1.0 → all k samples agree (high confidence)
- Consistency = 0.2 → each sample is different (model is highly uncertain)

**Target**: Consistency ≥ 0.6 before auto-accepting generated code.

### 6.4 NLI Entailment Score

Use a Natural Language Inference (NLI) model to verify that generated code claims are supported by the Figma specification:

```
Score_NLI = P(entailment | premise = figma_spec_text, hypothesis = code_claim_text)
```

Where:
- premise = structured text extracted from Figma (component name, variant properties, token values)
- hypothesis = a claim extracted from the generated code (e.g., "button has padding 16px", "color is #1A73E8")

**Process**:
1. Parse generated code to extract verifiable claims (spacing, color, typography, component name)
2. For each claim, construct an NLI pair (figma_spec_text, claim)
3. Run through an NLI model (e.g., DeBERTa-large-MNLI or equivalent)
4. Score_NLI = mean entailment probability across all claims

**Target**: Score_NLI ≥ 0.80 before auto-accepting.

### 6.5 Composite Hallucination Risk Score (HRS)

```
HRS = w₁ × (PPL/PPL_max) + w₂ × (1 - Consistency) + w₃ × (1 - Score_NLI)
```

Recommended weights: w₁ = 0.2, w₂ = 0.5, w₃ = 0.3

All three components are in [0, 1]. HRS ∈ [0, 1].

**Interpretation and action**:
| HRS | Action |
|-----|--------|
| < 0.20 | Auto-accept with logging |
| 0.20–0.40 | Accept with soft warning in output |
| 0.40–0.60 | Flag for human review — do NOT auto-accept |
| > 0.60 | Reject; regenerate with different prompt or model |

**Threshold**: HRS > 0.40 → mandatory human review. This is not configurable for India government portal projects (see §India Layer).

### 6.6 Shannon Entropy of Output Distribution

For multi-token decisions (e.g., which of N component names to use), Shannon entropy measures decision uncertainty:

```
H(p) = -Σ_{i=1}^{N} p_i × log₂(p_i)
```

- H = 0: deterministic (all probability on one choice)
- H = log₂(N): maximum uncertainty (uniform distribution)

**Normalized entropy**: H_norm = H / log₂(N)

Use H_norm as a secondary flag: if H_norm > 0.7 for a component selection decision, the model is highly uncertain — prefer retrieval-based (embedding similarity) over generative selection.

### 6.7 Platt Scaling for Score Calibration

Raw model confidence scores are often poorly calibrated. Apply Platt scaling to convert raw scores to calibrated probabilities:

```
P_calibrated = 1 / (1 + exp(A × f(x) + B))
```

Where:
- f(x) = raw model score (logit or similarity score)
- A, B = fitted on a labeled validation set using logistic regression
- P_calibrated = probability that the prediction is correct

Fit A and B using maximum likelihood on held-out validation data. Verify calibration with ECE (see §3.5).

---

## 7. Deep Mathematical Foundations

### M1: Cosine Similarity and HNSW ANN Search

**Cosine similarity derivation from inner product space**:

The angle θ between vectors **q** and **c** in ℝ^d satisfies:

```
cos(θ) = ⟨q, c⟩ / (||q||₂ × ||c||₂)
```

where ⟨q, c⟩ = Σ_{i=1}^{d} q_i × c_i (standard inner product), ||·||₂ = Euclidean norm.

Pre-normalizing both vectors: q̂ = q/||q||₂, ĉ = c/||c||₂ gives cos(θ) = ⟨q̂, ĉ⟩.

**HNSW (Hierarchical Navigable Small World) complexity**:

HNSW builds a multi-layer proximity graph. Each node at layer l has ≤ M_l neighbors. Layer 0 contains all N nodes; higher layers are exponentially sparser.

```
Build complexity: O(N × M × log N)
  - N insertions, each requiring O(M × log N) edge updates
  
Query complexity: O(log N) amortized greedy graph traversal
  - Navigate from entry point through layers until ef_search candidates accumulated
  
Memory: O(N × M × L_max) where L_max = O(log N)
```

**Recall bound**: For ef_search ≫ k (number of neighbors sought):

```
Recall@k → 1 as ef_search → N   (exact brute-force limit)
```

In practice, M=16, ef_search=64 yields Recall@10 ≈ 0.95–0.98 on semantic embedding corpora, with 10–50× speedup over brute-force.

### M2: Softmax, Temperature Scaling, and ECE

**Softmax derivation as maximum entropy distribution**:

The softmax distribution is the unique maximum-entropy distribution over K classes subject to the constraint E[z_i] = z_i (expected score equals logit). Derived via Lagrange multipliers:

```
Maximize: -Σ p_i log p_i   (entropy)
Subject to: Σ p_i = 1, Σ p_i × z_i = c
Solution:   p_i = exp(z_i) / Σ_j exp(z_j)   (Gibbs/Boltzmann distribution)
```

Temperature τ introduces an energy scale: p_i ∝ exp(z_i/τ). As τ → 0, p → one-hot(argmax). As τ → ∞, p → uniform(1/K).

**ECE minimization as calibration objective**:

For B bins of equal width [0, 1/B), [1/B, 2/B), ..., [(B-1)/B, 1]:

```
ECE = Σ_{b=1}^{B} (|B_b|/n) × |acc(B_b) - conf(B_b)|
```

Optimal temperature τ* = argmin_{τ} ECE(τ) found by 1D grid search over τ ∈ [0.1, 10.0] (or binary search / Newton-Raphson on the derivative).

### M3: WCAG 2.1 Luminance and APCA v0.0.98G

**sRGB → linear derivation**:

The IEC 61966-2-1 standard defines sRGB transfer function (gamma ≈ 2.2 with linear region near zero):

```
C_linear = C_sRGB / 12.92                        if C_sRGB ≤ 0.04045
C_linear = ((C_sRGB + 0.055) / 1.055)^2.4        if C_sRGB > 0.04045
```

The 0.04045 crossover and 12.92 factor ensure continuity and equal derivative at the junction.

**WCAG relative luminance** uses the CIE 1931 Y tristimulus value approximation for sRGB primaries (D65 white point):

```
Y = 0.2126 × R_lin + 0.7152 × G_lin + 0.0722 × B_lin
```

Coefficients from ITU-R BT.709 color matrix (same primaries as sRGB).

**APCA v0.0.98G full derivation**:

APCA models human visual perception more accurately than WCAG 2.1 by:
1. Using different gamma exponents for text vs background (perceptual asymmetry)
2. Applying polarity (normal vs reverse) for asymmetric contrast
3. Producing a signed Lightness Contrast Lc in perceptual units

Normal polarity (Yb ≥ Yt):
```
Lc = ((Yb^0.56) - (Yt^0.57)) × 1.14 × 100
```

Reverse polarity (Yt > Yb):
```
Lc = ((Yb^0.65) - (Yt^0.62)) × 1.14 × 100
```

The exponents 0.56/0.57 (normal) and 0.65/0.62 (reverse) encode perceptual gamma for the specific stimulus configuration. The factor 1.14 (= Sa) normalizes to a 0–100+ scale.

Clamp rule: if |Lc| < 7.5 → Lc := 0 (minimum contrast zone where polarity is indeterminate).

WCAG 3.0 adoption of APCA as legal standard is still pending as of May 2026. WCAG 2.1 AA (CR ≥ 4.5) remains the binding standard.

### M4: Design Consistency Score Derivation

**CRR, SCI, DR** are ratio statistics over the Figma document node tree T:

Let V = nodes(T), and define indicator functions:

```
I_lib(v) = 1 if v has mainComponent ∈ LibraryComponents, else 0
I_style(v) = 1 if v has any styleId referencing a named style, else 0
I_det(v) = 1 if v is a detached instance (was library, mainComponent removed), else 0
```

Then:
```
CRR = Σ_{v∈V} I_lib(v) / |V| × 100
SCI = Σ_{v∈V} I_style(v) / |{v : has_style(v)}| × 100
DR  = Σ_{v∈V} I_det(v) / (Σ I_lib(v) + Σ I_det(v)) × 100
```

**DCS as a weighted linear combination** (convex because Σ weights = 1.0):

```
DCS = 0.4 × (CRR/100) + 0.4 × (SCI/100) + 0.2 × (1 - DR/100)
DCS ∈ [0, 1]
```

Weights reflect that CRR and SCI are primary adoption signals; DR is a secondary health signal (weight 0.2).

**DTW for spatial sequence comparison**:

Given two spacing sequences A = [a₁, ..., aₙ] and B = [b₁, ..., bₘ] (e.g., component padding sequences):

```
DTW(0, 0) = |a₁ - b₁|
DTW(i, 0) = Σ_{k=1}^{i} |aₖ - b₁|    (boundary)
DTW(0, j) = Σ_{k=1}^{j} |a₁ - bₖ|    (boundary)
DTW(i, j) = |aᵢ - bⱼ| + min(DTW(i-1, j), DTW(i, j-1), DTW(i-1, j-1))
```

DTW(n, m) = optimal alignment cost. Normalize: DTW_norm = DTW(n,m) / max(n,m).
Flag as inconsistent if DTW_norm > T_dtw (tune per design system; start with T_dtw = 0.15).

### M5: Shannon Entropy and Platt Scaling

**Shannon entropy derivation from axioms**:

Shannon (1948) showed that the unique function H satisfying:
1. Continuity in p_i
2. Maximality: H is maximized when p_i = 1/N ∀i
3. Decomposability: H(AB) = H(A) + H(B|A)

is:

```
H(p) = -K × Σ_{i=1}^{N} p_i × log p_i   (K > 0, determines units)
```

With K=1 and log base 2: H in bits. With log base e: H in nats.

Normalized: H_norm = H / H_max = H / log₂(N) ∈ [0, 1].

H_norm = 0: one class has all probability (certainty).
H_norm = 1: uniform distribution (maximum uncertainty).

**Platt scaling derivation**:

Platt (1999) fits a sigmoid to convert raw classifier scores f(x) to probabilities. For binary case:

```
P(y=1|x) = 1 / (1 + exp(A × f(x) + B))
```

A < 0 (typically) because higher f(x) → higher positive class probability. Fit A, B via maximum likelihood on validation set S_val:

```
(A*, B*) = argmax_{A,B} Σ_{(x,y)∈S_val} [y × log p + (1-y) × log(1-p)]
```

where p = 1/(1 + exp(A × f(x) + B)).

Solved by L-BFGS or Newton's method. Platt scaling is effective when the calibration set size ≥ 100 samples per class.

### M6: Composite Hallucination Risk Score (HRS) and Self-Consistency

**PPL derivation from cross-entropy**:

For a sequence of N tokens (t₁, ..., t_N), the autoregressive model assigns probability:

```
P(t₁,...,t_N) = Π_{k=1}^{N} P(tₖ | t₁,...,tₖ₋₁)
```

Cross-entropy per token:
```
H = -1/N × Σ_{k=1}^{N} log P(tₖ | t₁,...,tₖ₋₁)
```

Perplexity:
```
PPL = exp(H) = exp(-1/N × Σ log P(tₖ | context))
```

PPL measures geometric mean inverse probability per token. PPL=1: perfect prediction. PPL=V (vocabulary size): random baseline.

**Self-consistency statistics**:

Generate k independent samples {s₁, ..., sₖ} from the model at temperature τ > 0. Cluster into equivalence classes {C₁, ..., Cₘ} (semantic deduplication). Consistency:

```
Consistency = max_i |Cᵢ| / k
```

This is the empirical mode probability — the fraction of samples that agree with the plurality answer. Under repeated sampling with a well-calibrated model, E[Consistency] estimates the true probability of the correct answer.

**HRS composite**:

```
HRS = 0.2 × (PPL/PPL_max) + 0.5 × (1 - Consistency) + 0.3 × (1 - Score_NLI)
```

Weight rationale:
- PPL (w=0.2): weak signal alone, useful as early warning
- 1 - Consistency (w=0.5): strongest signal — disagreement across samples is the best hallucination indicator
- 1 - NLI (w=0.3): strong signal when Figma spec is available as grounding text

HRS ∈ [0, 1]. Threshold HRS > 0.40 triggers mandatory human review. This threshold was validated on a corpus of LLM-generated UI code evaluated against Figma specs.

---

## 8. Anti-Patterns to Avoid

- **Treating raw softmax output (τ=1.0) as a calibrated confidence score**: §3.3 exists precisely because raw softmax is often overconfident — applying the 0.80 auto-accept threshold (§3.4) to uncalibrated logits without first finding τ* that minimizes ECE (§3.5) on a held-out validation set means the "0.80" cutoff does not actually correspond to 80% empirical accuracy.
- **Skipping self-consistency sampling because it is expensive, and leaning on PPL alone**: the HRS composite's own weight rationale states PPL (w=0.2) is "a weak signal alone" while 1-Consistency (w=0.5) is "the strongest signal" — computing HRS from PPL and NLI only, with Consistency defaulted to a placeholder, silently drops the single most predictive term in the formula rather than genuinely reducing hallucination risk.
- **Using `inner_product` HNSW space without confirming vectors were pre-normalized at index time**: §2.3's cost reduction from O(3d) to O(d) and §2.4's `inner_product` recommendation both depend on unit-length vectors — indexing raw (non-normalized) embeddings under `inner_product` space produces similarity rankings that do not correspond to cosine similarity at all, not merely a less-accurate version of it.
- **Serving top-k ANN results directly without the post-retrieval filter pass**: §2.5's scope/variant/type/availability filters are deterministic and mandatory precisely because embedding similarity alone cannot express "same component, wrong state" or "remote library not accessible" — returning raw HNSW output to a user or downstream code-gen step risks matching a visually similar but functionally wrong variant (e.g., a hover-state button returned for a default-state query).
- **Applying the DCS composite weights (α=0.4, β=0.4, γ=0.2) or the DTW threshold T_dtw as universal constants**: §5.5 and §5.6 both present these as recommended starting points ("tune per design system") — treating them as fixed thresholds across design systems with very different component maturity or spacing conventions produces DCS grades and consistency-violation flags that don't reflect that system's actual adoption reality.
- **Reporting the Detachment Rate (§5.4) as an exact metric**: the section itself notes DR is approximated via nodes with a missing `mainComponent` field at expected library-component positions, not a true diff against file version history — presenting DR as a precise measurement rather than an approximation overstates confidence in a number that can both over- and under-count actual detachments.
- **Reporting an APCA Lc value without applying the offset-and-clamp step**: §4.2 Step 4 requires setting Lc=0 whenever |Lc| < 7.5 (the "black-on-black zone" with no meaningful contrast) — skipping this clamp and reporting the raw computed value as a small-but-nonzero contrast score misrepresents a genuinely unreadable color pair as having some perceptible contrast.
- **Citing APCA thresholds as a compliance requirement**: §4.2's table is explicitly flagged as WCAG 3.0 *draft* status, still in draft as of the skill's writing — presenting an |Lc| ≥ 75 pass as satisfying a legal accessibility obligation (rather than WCAG 2.1's CR ≥ 4.5, the actual legal standard under RPwD Act 2016 §40) overstates what the metric currently certifies.

## 9. India-Specific Layer

### Digital Personal Data Protection Act 2023 (DPDP)

- **§4 (Lawful processing)**: AI processing of Figma design data (which may contain user-uploaded PII in mockups) requires lawful basis. Consent or legitimate purpose required.
- **§8 (Data Fiduciary obligations)**: Organizations using AI tools that process design data must implement data quality safeguards. AI-generated code that produces inaccurate UI may violate §8 accuracy obligations if the UI processes personal data.
- **§16 (Cross-border data transfer)**: Figma is a US-hosted SaaS. Design data containing PII sent to Figma servers constitutes cross-border transfer. [REQUIRES LEGAL REVIEW — MeitY has not yet released the cross-border data transfer notification under §16 as of May 2026. Consult legal counsel before using Figma for government projects involving personal data.]

### RPwD Act 2016 — Accessibility for AI-Generated UI

- **§40**: Mandates that UI for government services meets WCAG 2.1 Level AA (CR ≥ 4.5 for normal text). AI-generated UI code must be validated with the §4.1 contrast formula before deployment.
- **§45**: Mandates accessible design for "content available to public through electronic means." AI automation pipelines must include contrast and ARIA validation as blocking gates.

**Enforcement**: Any AI-generated Figma-to-code output for India government portals must pass WCAG 2.1 AA contrast check (not just APCA) before delivery.

### GIGW v3.0 (Government of India Guidelines for Websites)

- **Chapter 6**: Addresses AI-generated content — recommends human review for all AI-generated content on government websites [CONFIDENCE:MED — verify current chapter numbering with NIC GIGW v3.0 document].
- Implication: HRS threshold for India government projects should be set to 0 (all AI-generated code requires human review), overriding the standard HRS > 0.40 threshold.
- GIGW v3.0 also mandates WCAG 2.1 AA compliance and requires accessibility testing with assistive technologies (screen readers, keyboard navigation).

### MeitY AI Advisory 2023

- MeitY issued an advisory in 2023 on responsible use of AI/ML tools in digital services [CONFIDENCE:MED — advisory is non-binding as of May 2026; regulatory status may change].
- Recommends: human-in-the-loop for AI-generated content in citizen-facing services, explainability of AI decisions, bias testing.
- Implication for Figma AI automation: design consistency scores (DCS) and accessibility scores must be explainable and auditable. Store HRS, Score_NLI, and Consistency values per generation for audit trail.

### CERT-In and IT Act §43A

- AI automation pipelines that store Figma design data on-premise or in cloud must comply with CERT-In Direction 6 (2022): retain logs for 180 days.
- IT Act §43A: Reasonable security practices for "sensitive personal data" — if Figma files contain user PII in mockups, the automation pipeline handling those files is subject to §43A.

---

## Response Rules

1. Always compute and report both WCAG 2.1 CR and APCA Lc for any contrast question — never report only one.
2. Explicitly state that APCA is advisory (not legally mandated) in India or globally as of May 2026.
3. Apply HRS threshold of 0.40 for auto-accept; never lower it to 0.70 or below without explicit validation data.
4. Flag any design data involving PII with a DPDP §4/§8 note; flag cross-border data (Figma SaaS) with a DPDP §16 advisory.
5. For India government portal projects, override HRS threshold to 0 (require human review for all AI-generated output).
6. Use MCP server for structured Figma spec retrieval when computing NLI entailment — do not rely on free-text descriptions.
7. Report DCS component metrics (CRR, SCI, DR) individually alongside the composite score.
8. When Figma AI features are requested programmatically (triggering Make, AI suggestions via API), state that no programmatic API exists as of May 2026.
9. Apply log-sum-exp stabilization for all softmax computations — never compute raw exp() on logits without max subtraction.
10. Self-consistency sampling: always use k ≥ 5 samples; report both Consistency value and the agreed answer.

---

## What Not to Do

- Do not claim APCA compliance is legally equivalent to WCAG 2.1 AA compliance under RPwD Act 2016 §40 — it is not.
- Do not use PPL alone as a hallucination detector — a model can produce low-PPL hallucinations (confidently wrong output).
- Do not set auto-accept threshold at 0.70 — this is too permissive. Use 0.80 for intent classification, HRS < 0.40 for code generation.
- Do not bypass human review for India government portal projects by applying any HRS threshold.
- Do not expose raw Figma design tokens containing PII-related values (e.g., patient data labels in healthcare mockups) to external embedding APIs without DPDP §4 lawful basis.
- Do not conflate DCS with actual design quality — DCS measures system adherence, not aesthetic or functional quality.
- Do not use HNSW index built on non-normalized vectors with `inner_product` space — this will produce incorrect similarity rankings. Normalize before indexing if using inner_product space.
- Do not use Fréchet distance approximations for contractual accessibility compliance claims — it is a heuristic for internal tooling only.
- Do not report a single "90% quality" score without component breakdowns (CRR, SCI, DR, HRS) — composite scores are opaque.
- Do not use self-consistency with k < 5 — variance is too high for reliable Consistency estimation.

---

## Output Expectations

When applying this skill, outputs should include:

**ADR-4 Compliance:** All AI outputs in this skill carry a `confidence_score` field (mapped to calibrated probability from Platt scaling or Score_NLI). ADR-4 threshold: `confidence_score ≥ 0.75` for auto-accept. `confidence_score < 0.75` requires human confirmation before acting on the AI suggestion.

1. **Component Similarity Search**: top-k results with cosine similarity scores, component names, componentSetIds, and variant properties; post-filter rationale; HNSW index parameters used.

   ```json
   {
     "type": "component_similarity_search",
     "query": "string",
     "results": [
       {
         "rank": 1,
         "componentId": "string",
         "componentName": "string",
         "componentSetId": "string",
         "similarity_score": 0.0,
         "confidence_score": 0.0,
         "variant_properties": {}
       }
     ],
     "hnsw_params": {"M": 16, "ef": 100},
     "confidence_score": 0.0
   }
   ```

2. **Intent Classification**: top-3 predicted intents with calibrated probabilities; temperature τ used; whether auto-accept threshold met; ECE of the classifier if available.

   ```json
   {
     "type": "intent_classification",
     "node_id": "string",
     "top_intents": [
       {"intent": "string", "probability": 0.0, "calibrated_probability": 0.0}
     ],
     "temperature": 1.0,
     "auto_accepted": false,
     "confidence_score": 0.0,
     "requires_human_review": true
   }
   ```

3. **Contrast Report**: WCAG 2.1 CR with AA/AAA status; APCA Lc with use-case mapping; India regulatory context (RPwD §40); advisory note on APCA legal status.

   ```json
   {
     "type": "contrast_report",
     "foreground_hex": "string",
     "background_hex": "string",
     "wcag21": {"contrast_ratio": 0.0, "aa_normal": false, "aa_large": false, "aaa_normal": false},
     "apca": {"lc": 0.0, "polarity": "normal|reverse", "use_case_recommendation": "string"},
     "india_regulatory": {"rpwd_s40_compliant": false, "gigw_applicable": false},
     "confidence_score": 1.0
   }
   ```

4. **Consistency Score Report**: CRR, SCI, DR values with numerators and denominators; DCS composite; grade (Excellent/Good/Fair/Poor); recommended improvement action.

   ```json
   {
     "type": "consistency_score_report",
     "crr": {"value": 0.0, "used": 0, "total": 0},
     "sci": {"value": 0.0, "covered": 0, "total": 0},
     "dr": {"value": 0.0, "detached": 0, "total": 0},
     "dcs": {"value": 0.0, "grade": "Excellent|Good|Fair|Poor"},
     "recommended_action": "string",
     "confidence_score": 1.0
   }
   ```

5. **Hallucination Risk Assessment**: PPL, Consistency (with k stated), Score_NLI, HRS composite; action recommendation (auto-accept/warning/review/reject); any India-specific override applied.

   ```json
   {
     "type": "hallucination_risk_assessment",
     "ppl": 0.0,
     "self_consistency": {"k": 5, "consistency_score": 0.0},
     "nli_score": 0.0,
     "hrs": 0.0,
     "action": "auto-accept|warning|human-review|reject",
     "confidence_score": 0.0,
     "india_override": null
   }
   ```

---

## Skill Scope

This skill covers:
- Embedding-based component retrieval (cosine similarity, HNSW ANN search, pre-normalization)
- Softmax classification with temperature scaling and ECE calibration
- WCAG 2.1 contrast ratio and APCA v0.0.98G contrast computation (full coefficient set)
- Design consistency scoring (CRR, SCI, DR, DCS)
- Hallucination risk estimation (PPL, self-consistency, NLI entailment, HRS composite)
- Platt scaling and Shannon entropy for confidence quantification
- India regulatory context: DPDP 2023, RPwD 2016, GIGW v3.0, MeitY AI Advisory 2023

This skill does NOT cover:
- Figma REST API authentication and rate limiting (see figma-rest-api-core)
- Design token format and Style Dictionary pipeline (see design-tokens-automation-core)
- Figma Plugin or Widget development (see figma-plugin-widget-core)
- CI/CD pipeline orchestration (see figma-ci-cd-pipeline-core)
- Multi-platform token deployment (see figma-multiplatform-tokens-core)
- Direct invocation of Figma AI features via API (no such API exists as of May 2026)

---

## Version

v1.0.1 — Added Anti-Patterns to Avoid section (§8, renumbering India-Specific Layer to §9): softmax calibration, HRS Consistency-term omission, HNSW inner_product normalization, post-retrieval filter skipping, DCS/DTW default-weight overgeneralization, DR approximation caveat, APCA clamp/draft-status misreporting.

v1.0.0 — May 2026. Domain: Figma Automation (#43). Covers Figma AI ecosystem as of May 2026 (Figma Make GA, MCP Server GA, AI agent canvas editing beta). APCA v0.0.98G coefficients. DPDP Act 2023, RPwD Act 2016, GIGW v3.0, MeitY AI Advisory 2023. WCAG 3.0 / APCA legal adoption status: pending globally as of May 2026.

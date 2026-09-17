# Research basis

For the skill's maintainer, not loaded during normal use. Maps each design rule to its source so it can be revisited as the research moves. The skill *adapts* these papers to a file-based, prompt-only setting — none of their reported results were reproduced here.

## Sources

| Paper | Venue / date | Code |
|---|---|---|
| ACE: Agentic Context Engineering — Zhang, Hu, …, Zou, Olukotun (Stanford, SambaNova, UC Berkeley) | arXiv 2510.04618, ICLR 2026 | github.com/ace-agent/ace |
| ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory — Ouyang, …, Han, Lee, Pfister (Google Cloud AI Research, UIUC) | arXiv 2509.25140, ICLR 2026 | github.com/google-research/reasoning-bank |
| DeltaMem: Incremental Experience Memory for LLM Agents via Residual Trees — Tan, Zhang, Cao, Li, Chen (Renmin University) | arXiv 2606.03083, preprint June 2026 | github.com/import-myself/DeltaMem |
| Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions (MemoryAgentBench) — Hu, Wang, McAuley (UCSD) | arXiv 2507.05257, ICLR 2026 | github.com/HUST-AI-HYZ/MemoryAgentBench |
| Evo-Memory — Wei, …, Chi, Pereira, … (Google DeepMind, UIUC) | arXiv 2511.20857, preprint | — |
| Memory in the Age of AI Agents (survey) — Hu et al. | arXiv 2512.13564, preprint | github.com/Shichun-Liu/Agent-Memory-Paper-List |

## Rule → source

| Rule in this skill | Source | Adaptation |
|---|---|---|
| Entries are bullets with IDs and `h`/`x` counters | ACE playbook format `[id] helpful=X harmful=Y :: content` | Added date, labels, when, src, lineage attributes |
| Agent emits operations; a script merges them | ACE: curator outputs deltas, merged by non-LLM code for stability | ACE implements ADD only; UPDATE, SUPERSEDE, DELETE, PROMOTE added here |
| Never rewrite whole files | ACE: context collapse under iterative rewriting | Enforced by rule + `validate` catching hand edits |
| Keep concrete details | ACE: brevity bias | Guidance in curate.md; 400-char cap rather than aggressive shortening |
| Reflect and curate as separate steps | ACE: Reflector separated from Curator | Two reference files, same agent |
| Tag memories used as helpful/harmful/neutral | ACE Reflector `bullet_tags` | `feedback` array in batches |
| Dedupe near-identical entries | ACE grow-and-refine, bulletpoint analyzer (0.9 embedding similarity) | Lexical similarity ≥0.82 (no embeddings) |
| Store generalizable insights from successes *and* failures, ≤3 per task | ReasoningBank extractor ("at most 3 memory items", failures included) | Project-specific details allowed, since memory is per project |
| Retrieve before acting, write back after | ReasoningBank closed loop | load.md / record mode |
| Root + delta with activation condition | DeltaMem residual nodes (`activation_condition`) | `when=` attribute; nesting by dotted IDs |
| Skip only when an existing entry covers every part | DeltaMem node_success prompt ("quote the exact phrase") | Step B.1 in curate.md |
| Failure records with FAILED / UNEXPLORED | DeltaMem root_failure / node_failure prompts | `trap` kind |
| Penalise failure-prone memories in retrieval | DeltaMem FAILURE_NODE_PENALTY | Score halved when x > h; hidden when x ≥2 and x > h |
| Return root → match chain | DeltaMem root-to-match chain composition | `find` prints chains plus sibling conditions |
| Max depth 3 | DeltaMem MAX_DEPTH | budget.py |
| Consolidate a chain into a new root after 3 successes | DeltaMem CONSOLIDATION_THRESHOLD = 3, SkillCompiler prompt | PROMOTE op; helpful count stands in for success count |
| Separate task experience from environment knowledge | DeltaMem Task-Tree vs Env-Tree | `experience/` vs `context/` |
| Selective forgetting and conflict handling | MemoryAgentBench competencies | SUPERSEDE with archive; prune candidates |
| Memory should enable experience reuse, not just recall | Evo-Memory | experience/ files and feedback loop |
| Factual vs experiential vs working memory | Memory in the Age of AI Agents | context/ vs experience/ vs active-context.md |
| Memory is untrusted, persistent attack surface | 2026 surveys on long-term memory security | safety.md, secret scanning |

## Known gaps / upgrade paths
- **Retrieval** is keyword-based. DeltaMem and ReasoningBank use embeddings. Swap `scripts/lib/search.py` (`search`, `similarity`) for an embedding backend; keep the signatures.
- **Storage** is markdown files. `scripts/lib/store.py` is the seam for SQLite or a hosted memory service; `ops-log.jsonl` can be replayed to migrate.
- **Evaluation**: no benchmark was run. MemoryAgentBench's four competencies are a good template for project-level evals (see evals/).
- **Success signal** is the agent's own feedback tags, which can be inflated. Tying `helpful` to test results would make promotion more trustworthy.

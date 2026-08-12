# ClaimCheck

Verify an investor deck against a data room of SEC filings, and cite the exact
passage behind every verdict.

**[Live demo](https://ui-indol-psi.vercel.app)** · **[Architecture](https://ui-indol-psi.vercel.app/architecture)**

---

## The problem, in four lines

Split a 10-K at 512 tokens and this happens:

```
chunk 41   "... Revenue   Cost of revenue   Gross profit ..."     labels, no numbers
chunk 42   "... 2,684,275   2,128,359   515,531   409,908 ..."    numbers, no labels, no years
```

Retrieve chunk 42 and the model sees a pile of digits with no idea which is
revenue and which is FY2023. It answers anyway, confidently, with a number that
means nothing. On financial tables that is not an edge case, it is the norm.

The second problem is subtler: **most discrepancies are not lies.** A deck
reporting $674M non-GAAP operating income against a filing's $54M GAAP figure
is not deception, it is a different basis. A tool that calls that a
contradiction gets closed by the third false alarm.

## How it works

```
INGEST      filings → markdown → a tree of their own sections
            121 nodes for the 10-K, holding titles and spans but no text
            nothing chunked, so tables keep their row labels and years

EXTRACT     the deck goes in whole; the model tags each figure
            value · scale · unit · period — Python does the multiplying

VERIFY      a ReAct agent: claims are the query, the corpus is the environment
            four tools, turn-budgeted, batched so claims share a fetch
            the agent reads and states each verdict

VALIDATE    deterministic, no model: is the cited figure actually in the text
            it fetched? does the node resolve? is the citation real?
            a verdict whose evidence fails becomes NO_EVIDENCE with a reason
```

**The agent verifies the claim. Code verifies the agent supplied the evidence
for it.**

Verdicts: `SUPPORTED` · `CONTRADICTED` · `BASIS_MISMATCH` · `NO_EVIDENCE` · `NO_SOURCE`

## Benchmark

Twelve cases with expectations verified by hand against Datadog's FY2024 10-K:
six figures that must pass, four seeded defects that must be caught (inflated
revenue, wrong growth rate, 10× operating income, millions stated as billions),
one GAAP versus non-GAAP basis difference, and one claim no filing covers.

Same cases, five open-weight models, one agent run each, run concurrently.

| model | correct | time | evidence rejected |
|---|---|---|---|
| `qwen/qwen3-235b-a22b-2507` | **12/12** | 54s | 0 |
| `z-ai/glm-4.7-flash` | 11/12 | 70s | 0 |
| `deepseek/deepseek-v4-flash` | 8/12 | 98s | 5 |
| `moonshotai/kimi-k2.6` | 1/12 | 71s | 12 |
| `nvidia/nemotron-3-super-120b-a12b` | 1/12 | 415s | 12 |

Qwen, three consecutive runs: **12/12, 12/12, 12/12** in 100s, 106s, 107s, zero
rejections. It is the default.

**Read the rejection column first.** It counts findings the validator refused
because the evidence behind them did not hold up:

- DeepSeek reported five figures that are real and correct, but cited sections
  that do not contain them. Right numbers, wrong citation. That looks perfect
  in a demo and falls apart the moment a reviewer clicks a link.
- Nemotron and Kimi never produced parseable findings at all.

A model scoring 10/12 with two rejections is worse than one scoring 9/12 with
none, because invented evidence is the failure you cannot see coming.

### What this benchmark is not

Twelve cases is a spot check. It identifies a broken model; it cannot tell you
11/12 beats 12/12. The agent states the verdict, so results are not
reproducible run to run, which is why the winner was run three times. No
precision, recall or F1 is reported, because a hand-counted set of twelve
cannot support them.

## Found by running it

Each of these shipped, ran against a real filing, and produced a wrong result
that looked like a right one. All are now regression tests.

**The agent invented evidence.** It reported `674,000` for non-GAAP operating
income and the system returned `SUPPORTED` with a working citation. That figure
is not in the filing. It had the text in context and produced a plausible
number anyway. Every figure is now checked against the text actually fetched.

**The deck verified itself.** The agent read the earnings release as evidence
for the earnings release's own claims and reported agreement. Documents now
carry a role and the prompt refuses to cite an assertion as its own evidence.

**A correct figure was rejected.** `$54 million` against a retrieved `54,284`
failed as `unit mismatch: USD vs count`. A bare number lifted from a table is
not asserting that it isn't money; the currency sits in the column header.

**Six of thirty-five claims were verified.** A token guard from development
capped the UI at six and truncated silently. Claims now run in groups with a
check that verdict count matches claim count.

## Run it

```bash
pip install -r requirements.txt

export LLM_BASE_URL=https://openrouter.ai/api/v1     # or Groq, vLLM, Ollama
export LLM_MODEL="qwen/qwen3-235b-a22b-2507"
export LLM_API_KEY=...

python3 -m pytest tests -q          # 106 tests, no API key needed
python3 benchmark.py --judge        # the 12 cases above
python3 compare_models.py           # several models, in parallel

VERIFY_ENABLED=1 uvicorn src.api:app --port 8000
cd ui && python3 -m http.server 8777      # then open localhost:8777
```

Open-weight models only, over an OpenAI-compatible endpoint, so the provider is
one environment variable. No OpenAI, no Anthropic. Qwen3 is Apache 2.0.

## Where this breaks

**Entity claims are dropped.** `search` (BM25) is specified and unbuilt, so
"Acme Corp is a customer" never reaches verification. This checks figures, not
claims in general.

**Latency.** Roughly 20s per claim batched, and turns dominate: each one is a
full round trip carrying the whole conversation. Preloading the section tree
into the prompt would remove two turns per run.

**Node summaries were never generated.** The agent selects sections from titles
alone, so it guesses wrong and re-fetches more than it should.

**Documents need recoverable structure.** Every SEC filing has a table of
contents; arbitrary PDFs do not. Scanned pages, image-only charts and
spreadsheets yield nothing.

**Single process.** The tree cache and run state are one node each.

**Verdicts are not reproducible.** The agent decides, so the same deck can
produce a different verdict on a rerun. `src/compare.py` still holds a
deterministic verdict path with its own tests, kept as a second opinion.

## Layout

```
src/loader.py      pdf · html · md → markdown, tables intact
src/tree.py        section tree, no text in nodes, cached by sha256
src/tools.py       list_documents · get_structure · get_content
src/extract.py     deck → typed, tagged claims
src/verify.py      ReAct loop, evidence only
src/judge.py       ReAct loop, agent states the verdict     ← default path
src/validator.py   the contract check
src/compare.py     deterministic verdicts                   ← second opinion
src/api.py         FastAPI + SSE
ui/                the workpaper
```

Figures throughout are from Datadog, Inc.'s FY2024 Form 10-K, filed 20 February
2025, and its Q4 FY2024 earnings release.

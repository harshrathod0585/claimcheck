import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  AlertCircle,
  FileText,
  Sparkles,
  Search,
  Clock,
  UploadCloud,
  ExternalLink,
  Activity,
  Settings,
  Trash2,
  Zap,
  Cpu
} from 'lucide-react'
import type { Claim, Doc, Status, Verdict } from './api'

export function TickIcon({ status, size = 18 }: { status: Status; size?: number }) {
  switch (status) {
    case 'SUPPORTED':
      return <CheckCircle2 size={size} className="icon-supported" />
    case 'CONTRADICTED':
      return <XCircle size={size} className="icon-contradicted" />
    case 'BASIS_MISMATCH':
      return <AlertTriangle size={size} className="icon-basis" />
    case 'RUN_FAILED':
      return <AlertCircle size={size} className="icon-contradicted" />
    case 'NO_EVIDENCE':
    case 'NO_SOURCE':
    default:
      return <HelpCircle size={size} className="icon-none" />
  }
}

const TONE: Record<Status, string> = {
  SUPPORTED: 'supported',
  CONTRADICTED: 'contradicted',
  BASIS_MISMATCH: 'basis',
  NO_EVIDENCE: 'none',
  NO_SOURCE: 'none',
  RUN_FAILED: 'contradicted',
}

const LABEL: Record<Status, string> = {
  SUPPORTED: 'TRACED & VERIFIED',
  CONTRADICTED: 'EXCEPTION DETECTED',
  BASIS_MISMATCH: 'BASIS DIFFERENCE',
  NO_EVIDENCE: 'NOT LOCATED IN FILING',
  NO_SOURCE: 'NO EVIDENCE SOURCE',
  RUN_FAILED: 'RUN FAILED',
}

export function Elapsed({ from }: { from: number }) {
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setSecs(Math.round((Date.now() - from) / 1000)), 1000)
    return () => clearInterval(id)
  }, [from])
  return (
    <span className="secs-badge">
      <Clock size={12} />
      <b>{secs}s</b>
    </span>
  )
}

export function DocList({
  title,
  docs,
  role,
  onUpload,
  onFetch,
  onRemove,
  live,
  busy,
  uploadProgress = 0,
}: {
  title: string
  docs: Doc[]
  role: 'deck' | 'room'
  onUpload: (files: FileList) => void
  onFetch: (url: string) => void
  onRemove?: (doc_id: string) => void
  live: boolean
  busy: boolean
  uploadProgress?: number
}) {
  const [url, setUrl] = useState('')
  const [over, setOver] = useState(false)

  return (
    <div
      className={`drop${over ? ' over' : ''}`}
      onDragEnter={e => { e.preventDefault(); setOver(true) }}
      onDragOver={e => { e.preventDefault(); setOver(true) }}
      onDragLeave={e => { e.preventDefault(); setOver(false) }}
      onDrop={e => { e.preventDefault(); setOver(false); onUpload(e.dataTransfer.files) }}
    >
      <div className="drop-role">
        <FileText size={14} className="icon-inline" /> {title}
      </div>

      {busy && uploadProgress > 0 && (
        <div className="context-progress-bar">
          <div className="context-progress-info">
            <div className="context-label">
              <UploadCloud size={13} className="pulse-icon icon-inline" />
              <span>Pre-processing & Indexing Document Tree...</span>
            </div>
            <span className="context-pct">{uploadProgress}%</span>
          </div>
          <div className="context-track">
            <div className="context-fill" style={{ width: `${uploadProgress}%` }}>
              <div className="context-shimmer" />
            </div>
          </div>
        </div>
      )}

      {docs.length === 0 ? (
        <div className="empty">
          <UploadCloud size={20} style={{ opacity: 0.5, marginBottom: 4 }} />
          <div>nothing yet — {role === 'deck' ? 'add pitch presentation decks to check' : 'add SEC filings to check against'}</div>
        </div>
      ) : (
        <ul className="docs">
          {docs.map(d => (
            <li key={d.doc_id}>
              <CheckCircle2 size={14} className="rcv" />
              <span className="doc-name">{d.doc_id}</span>
              <em>{d.period ?? d.type}</em>
              {live && onRemove && (
                <button
                  type="button"
                  className="doc-remove-btn"
                  title={`Remove ${d.doc_id}`}
                  onClick={e => {
                    e.stopPropagation()
                    onRemove(d.doc_id)
                  }}
                >
                  <Trash2 size={13} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {live && (
        <>
          <label className="cta">
            <input
              type="file"
              accept=".pdf,.htm,.html,.md"
              multiple
              hidden
              onChange={e => {
                if (e.target.files?.length) onUpload(e.target.files)
                e.target.value = ''
              }}
            />
            <UploadCloud size={14} className="cta-icon" />
            <span>Drop {role === 'deck' ? 'a deck' : 'filings'} here, or <u>choose</u> (pdf · html · md)</span>
          </label>

          <form
            className="url-row"
            onSubmit={e => {
              e.preventDefault()
              if (!url.trim()) return
              onFetch(url.trim())
              setUrl('')
            }}
          >
            <input
              type="url"
              value={url}
              placeholder="or paste SEC filing URL..."
              onChange={e => setUrl(e.target.value)}
            />
            <button type="submit" disabled={busy}>
              {busy ? '...' : 'Fetch'}
            </button>
          </form>
        </>
      )}
    </div>
  )
}

export function ClaimsInspector({ claims }: { claims: Claim[] }) {
  const [filterOp, setFilterOp] = useState<string>('all')
  const [search, setSearch] = useState<string>('')

  if (!claims.length)
    return (
      <div className="extracted-container empty-extracted">
        <Sparkles size={22} className="icon-faint" />
        <span>No claims extracted yet — click <strong>1. Extract Claims</strong> in the header to parse the presentation deck.</span>
      </div>
    )

  const ops = Array.from(new Set(claims.map(c => c.operation)))
  const filtered = claims.filter(c => {
    const matchOp = filterOp === 'all' || c.operation === filterOp
    const matchSearch = !search || c.text.toLowerCase().includes(search.toLowerCase()) || c.figure.includes(search)
    return matchOp && matchSearch
  })

  return (
    <div className="claims-inspector-wrap">
      <div className="inspector-toolbar">
        <div className="inspector-title">
          <Sparkles size={14} />
          <span>Extracted Assertions ({claims.length} total)</span>
        </div>

        <div className="inspector-controls">
          <div className="search-box">
            <Search size={14} className="search-icon" />
            <input
              type="text"
              placeholder="Filter claims by keyword or figure..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div className="op-filters">
            <button
              className={`op-filter-btn ${filterOp === 'all' ? 'active' : ''}`}
              onClick={() => setFilterOp('all')}
            >
              All ({claims.length})
            </button>
            {ops.map(op => (
              <button
                key={op}
                className={`op-filter-btn ${filterOp === op ? 'active' : ''}`}
                onClick={() => setFilterOp(op)}
              >
                {op} ({claims.filter(c => c.operation === op).length})
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="claims-grid">
        {filtered.map((c, i) => (
          <div key={i} className="claim-card">
            <div className="claim-card-head">
              <span className={`claim-op-pill op-${c.operation}`}>{c.operation}</span>
              {c.figure && <span className="claim-figure-tag">{c.figure}</span>}
              <span className="claim-period-tag">{c.period || 'Period Unspecified'}</span>
            </div>
            <div className="claim-card-body">"{c.text}"</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Tally({ verdicts }: { verdicts: Verdict[] }) {
  const n = (...s: Status[]) => verdicts.filter(v => s.includes(v.status)).length
  const cells: [string, string, number, React.ReactNode][] = [
    ['supported', 'Traced (Verified)', n('SUPPORTED'), <CheckCircle2 size={16} key="s" />],
    ['contradicted', 'Exceptions (Mismatches)', n('CONTRADICTED', 'RUN_FAILED'), <XCircle size={16} key="c" />],
    ['basis', 'Basis Differences', n('BASIS_MISMATCH'), <AlertTriangle size={16} key="b" />],
    ['none', 'Not Located', n('NO_EVIDENCE', 'NO_SOURCE'), <HelpCircle size={16} key="n" />],
  ]

  return (
    <div className="tally">
      {cells.map(([cls, lbl, num, icon]) => (
        <div key={lbl} className={cls}>
          <div className="l">
            {icon} <span>{lbl}</span>
          </div>
          <span className="n">{num}</span>
        </div>
      ))}
    </div>
  )
}

export function ActiveSpotlight({
  phase,
  status,
  verdicts,
  claimsCount,
}: {
  phase: string
  status: string
  verdicts: Verdict[]
  claimsCount: number
}) {
  if (phase !== 'extracting' && phase !== 'verifying') return null

  const isVerifying = phase === 'verifying'
  const pct = isVerifying
    ? claimsCount > 0
      ? Math.min(100, Math.round((verdicts.length / claimsCount) * 100))
      : 30
    : 45

  return (
    <div className="hero-spotlight">
      <div className="hero-spotlight-row1">
        <div className="hero-badge">
          <Zap size={14} className="hero-zap" />
          <span>{isVerifying ? 'AGENT VERIFICATION RUN ACTIVE' : 'PARSING PITCH DECK'}</span>
        </div>
        <div className="hero-status-box">{status}</div>
      </div>

      <div className="hero-spotlight-row2">
        <div className="hero-subtext">
          <Cpu size={14} className="hero-cpu" />
          <span>
            {isVerifying
              ? `Evaluating claim ${Math.min(verdicts.length + 1, claimsCount)} of ${claimsCount}...`
              : 'Discarding marketing fluff and extracting factual metrics...'}
          </span>
        </div>
        <span className="hero-pct-tag">{pct}%</span>
      </div>

      <div className="hero-track">
        <div className="hero-fill" style={{ width: `${pct}%` }}>
          <div className="hero-shimmer" />
        </div>
      </div>
    </div>
  )
}

export function VerdictRow({ v }: { v: Verdict }) {
  const tone = TONE[v.status] ?? 'none'

  return (
    <div className={`claim claim-${tone}`}>
      <div className="tick">
        <TickIcon status={v.status} size={22} />
      </div>

      <div className="claim-main-content">
        <div className="claim-text">{v.text}</div>

        {v.reason && (
          <div className={`exception ${v.status === 'BASIS_MISMATCH' ? 'basis' : ''}`}>
            {v.reason}
          </div>
        )}

        {v.found && (
          <div className="decided">
            <span>Actual Filing Figure</span>
            {v.found}
          </div>
        )}

        {v.rejected && (
          <div className="decided err">
            <span>REJECTED FINDING</span>
            {v.rejected}
          </div>
        )}

        {v.quote && (
          <blockquote className="quoted">
            "{v.quote}"
          </blockquote>
        )}

        {v.cite ? (
          <a className="src" href={v.cite} target="_blank" rel="noreferrer">
            <span className="src-host">SEC EDGAR</span>
            <div className="src-body">
              <b>Primary SEC Citation Link</b>
              <div className="src-sec">{v.cite}</div>
            </div>
            <ExternalLink size={14} className="src-go" />
          </a>
        ) : (v.doc_id || v.node_ids?.length) ? (
          <div className="src-local">
            <FileText size={14} className="src-local-icon" />
            <div className="src-body">
              <b>Source Document: {v.doc_id || 'Corpus File'}</b>
              <div className="src-sec">
                {v.node_ids?.length ? `Verified Node ${v.node_ids.join(', ')}` : 'Document Node'}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className={`status ${tone}`}>
        <span className="status-badge">{LABEL[v.status] ?? v.status}</span>
      </div>
    </div>
  )
}

export interface TapeLine {
  id: number
  turn?: number
  call?: string
  args?: string
  mark?: string
  think?: string
  tone?: string
  ticking?: number
}

export function Tape({ lines }: { lines: TapeLine[] }) {
  return (
    <div className="tape">
      <div className="tape-head">
        <div className="tape-title">
          <Activity size={14} /> <span>AUDIT TAPE LOG</span>
        </div>
        <span className="live-dot" />
      </div>

      <div className="tape-body" ref={r => { if (r) r.scrollTop = r.scrollHeight }}>
        {lines.length === 0 ? (
          <div className="t-line t-empty">
            <Clock size={12} className="icon-faint" />
            <span>Waiting for verification run...</span>
          </div>
        ) : (
          lines.map(l => (
            <div key={l.id} className="tape-step-block">
              {l.turn !== undefined && (
                <div className="tape-step-num">
                  {String(l.turn).padStart(2, '0')}
                </div>
              )}

              {l.call && (
                <div className="tape-call-line">
                  <code>{l.call}</code>
                  {l.args && <span>({l.args})</span>}
                </div>
              )}

              {l.think && <div className="tape-think-text">{l.think}</div>}

              {l.mark && (
                <div className={`tape-mark-line ${l.tone ? TONE[l.tone as Status] || l.tone : ''}`}>
                  {l.tone === 'SUPPORTED' || l.tone === 'supported' ? '✓ traced — ' :
                   l.tone === 'CONTRADICTED' || l.tone === 'contradicted' ? '✗ exception — ' :
                   l.tone === 'BASIS_MISMATCH' || l.tone === 'basis' ? '≠ basis differs — ' :
                   l.tone === 'NO_EVIDENCE' || l.tone === 'NO_SOURCE' || l.tone === 'none' ? '? not located — ' : ''}
                  {l.mark}
                </div>
              )}

              {l.ticking && <Elapsed from={l.ticking} />}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export function ArchitectureView() {
  return (
    <div className="arch-view">
      <div className="intro-card">
        <p>
          ClaimCheck verifies every factual assertion in an investor pitch deck against a data room of SEC filings, and cites exact locations for each verdict. Two core principles drive the system design:
          <strong> 1. Financial numbers live inside structured tables</strong> that must never be severed by naive vector chunking, and
          <strong> 2. Most discrepancies are not lies</strong> — they are metrics measured on different accounting bases (e.g. Non-GAAP vs. GAAP).
        </p>
      </div>

      <section className="section-block">
        <div className="section-title">
          <Activity size={16} /> <span>System Data Flow</span>
        </div>
        <div className="arch-card">
          <p>
            <strong>Pipeline Lifecycle:</strong> Standard document processing follows a 4-tier pipeline: Index & Parse → Extract Claims → Investigate (Group Batch = 8) → Ground & Decide in Python.
          </p>
          <div className="stages-grid">
            <div className="stage-box">
              <div className="stage-num">01 · INDEX & PARSE</div>
              <h4>Document Loader</h4>
              <p>Converts HTML/PDF/Markdown to structured trees with table grids intact. Sha256 content cached.</p>
              <span className="tag-py">Deterministic</span>
            </div>

            <div className="stage-box">
              <div className="stage-num">02 · EXTRACT CLAIMS</div>
              <h4>Claim Extractor</h4>
              <p>Parses entire pitch deck, isolates factual assertions, and discards marketing fluff & projections.</p>
              <span className="tag-llm">1 LLM Call</span>
            </div>

            <div className="stage-box">
              <div className="stage-num">03 · INVESTIGATE</div>
              <h4>Verification Agent</h4>
              <p>Claims grouped in batches of 8. Agent navigates section trees & fetches content under dynamic turn budget.</p>
              <span className="tag-llm">Batched Agent</span>
            </div>

            <div className="stage-box">
              <div className="stage-num">04 · DECIDE</div>
              <h4>Ground & Decide</h4>
              <p>Python checks evidence grounding, parses metrics/periods, recomputes math, and assigns final verdicts.</p>
              <span className="tag-py">73 Unit Tests</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-title">
          <FileText size={16} /> <span>Why Tree Navigation Beats Vector RAG</span>
        </div>
        <div className="arch-card">
          <div className="callout key">
            <p>
              <strong>The Chunk Severance Flaw:</strong> Slicing financial tables into arbitrary 512-token vector chunks severs numbers from header rows and scale statements <code>(in thousands)</code>. The model attempts to guess column years, leading to off-by-1,000x errors. Tree navigation preserves HTML tables in full, keeping row labels and fiscal periods permanently attached.
            </p>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-title">
          <Settings size={16} /> <span>Verification Agent Tools & Environment Config</span>
        </div>
        <div className="arch-card">
          <table>
            <thead>
              <tr><th>Tool / Variable</th><th>Function / Default</th><th>Engineering Rationale</th></tr>
            </thead>
            <tbody>
              <tr><td><code>list_documents()</code></td><td>List corpus index & periods</td><td>Establishes filing coverage to prevent false contradictions.</td></tr>
              <tr><td><code>get_structure(doc)</code></td><td>Tree outline (no text)</td><td>Small enough to fit whole document tree in one prompt.</td></tr>
              <tr><td><code>get_content(doc, ids)</code></td><td>Intact Markdown tables & URL</td><td>Batched fetch returning primary citation links.</td></tr>
              <tr><td><code>search(query)</code></td><td>BM25 candidate search</td><td>Keyword search superior to vectors for proper nouns.</td></tr>
              <tr><td><code>LLM_BASE_URL</code></td><td><code>https://openrouter.ai/api/v1</code></td><td>OpenAI-compatible endpoint (Groq, OpenRouter, Ollama).</td></tr>
              <tr><td><code>LLM_MODEL</code></td><td><code>qwen/qwen3-235b-a22b-2507</code></td><td>Open-weight reasoning model used for investigation.</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

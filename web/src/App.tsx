import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Sparkles,
  FileCheck2,
  Filter,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Layers,
  ArrowRight
} from 'lucide-react'
import * as api from './api'
import type { Claim, Doc, Verdict } from './api'
import {
  ActiveSpotlight,
  ClaimsInspector,
  DocList,
  Tally,
  Tape,
  VerdictRow,
  type TapeLine
} from './components'

/** Claims per agent run. Claims sharing evidence share a fetch — that is the
 *  point of batching, and one run per claim re-reads the same table each time. */
const GROUP = 8

export default function App() {
  const [live, setLive] = useState(false)
  const [docs, setDocs] = useState<Doc[]>([])
  const [claims, setClaims] = useState<Claim[]>([])
  const [verdicts, setVerdicts] = useState<Verdict[]>([])
  const [lines, setLines] = useState<TapeLine[]>([])
  const [status, setStatus] = useState('idle')
  const [phase, setPhase] = useState<'idle' | 'extracting' | 'extracted' | 'verifying' | 'done'>('idle')
  const [busy, setBusy] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<'all' | 'SUPPORTED' | 'CONTRADICTED' | 'BASIS_MISMATCH'>('all')
  const nextId = useRef(0)

  const say = useCallback((line: Omit<TapeLine, 'id'>) => {
    setLines(ls => {
      // Only the newest line ticks; earlier ones freeze at their final time.
      const frozen = ls.map(l => (l.ticking ? { ...l, ticking: undefined } : l))
      return [...frozen, { ...line, id: nextId.current++ }]
    })
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [h, d] = await Promise.all([api.health(), api.documents()])
      setLive(h.live_verify)
      setDocs(d)
      setError('')
    } catch {
      setLive(false)
      setDocs([])
      setError('backend disconnected — start server with: uvicorn src.api:app --port 8000')
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const deck = docs.filter(d => d.role.startsWith('assertion'))
  const room = docs.filter(d => !d.role.startsWith('assertion'))

  async function doUpload(role: 'deck' | 'room', files: FileList | File[]) {
    if (!files || !files.length) return
    setBusy(true)
    setUploadProgress(15)

    const timer = setInterval(() => {
      setUploadProgress(p => (p < 85 ? p + 15 : p))
    }, 150)

    try {
      const res = await api.upload(role, files)
      clearInterval(timer)
      setUploadProgress(100)
      for (const doc of res.documents)
        if (!doc.ok) say({ mark: `${doc.name}: ${doc.detail}`, tone: 'contradicted' })
      await refresh()
    } catch (e) {
      clearInterval(timer)
      say({ mark: `upload failed · ${String(e).slice(0, 70)}`, tone: 'contradicted' })
    } finally {
      setTimeout(() => {
        setBusy(false)
        setUploadProgress(0)
      }, 400)
    }
  }

  async function doFetch(url: string) {
    setBusy(true)
    setUploadProgress(20)
    say({ call: 'fetch', args: url.split('/').pop() ?? url, ticking: Date.now() })

    const timer = setInterval(() => {
      setUploadProgress(p => (p < 85 ? p + 15 : p))
    }, 150)

    try {
      const r = await api.fetchUrl(url)
      clearInterval(timer)
      setUploadProgress(100)
      say({ mark: `${r.doc_id} · ${r.nodes} sections indexed` })
      await refresh()
    } catch (e) {
      clearInterval(timer)
      say({ mark: `fetch failed · ${String(e).slice(0, 80)}`, tone: 'contradicted' })
    } finally {
      setTimeout(() => {
        setBusy(false)
        setUploadProgress(0)
      }, 400)
    }
  }

  async function doRemove(doc_id: string) {
    try {
      await api.removeDocument(doc_id)
      say({ mark: `removed document ${doc_id}` })
      await refresh()
    } catch (e) {
      say({ mark: `remove failed · ${String(e).slice(0, 70)}`, tone: 'contradicted' })
    }
  }

  async function doExtract() {
    if (!deck.length) { setError('Please upload a deck document first'); return }
    setPhase('extracting'); setStatus('Parsing pitch deck documents and extracting statements...'); setError('')
    say({ call: 'extract', args: `${deck.length} deck(s)`, ticking: Date.now() })

    const allClaims: Claim[] = []
    try {
      for (const d of deck) {
        say({ mark: `extracting assertions from ${d.doc_id}` })
        const { claims: found } = await api.extract(d.doc_id)
        allClaims.push(...found)
      }
      setClaims(allClaims)
      say({ mark: `${allClaims.length} claims extracted across ${deck.length} deck(s)` })
      setStatus(`${allClaims.length} claims extracted`); setPhase('extracted')
    } catch (e) {
      say({ mark: `extract failed · ${String(e).slice(0, 90)}`, tone: 'contradicted' })
      setStatus('extract failed'); setPhase('idle')
      setError(String(e).slice(0, 160))
    }
  }

  async function doVerify() {
    if (!room.length) { setError('Please add at least one evidence filing to check against'); return }
    setPhase('verifying'); setVerdicts([]); setError('')

    const groups: Claim[][] = []
    for (let i = 0; i < claims.length; i += GROUP) groups.push(claims.slice(i, i + GROUP))
    say({ call: 'verify', args: `${claims.length} claims · ${groups.length} group(s)` })

    let seen = 0
    for (const [gi, group] of groups.entries()) {
      say({ mark: `group ${gi + 1}/${groups.length} · ${group.length} claims` })
      try {
        for await (const ev of api.verify(group)) {
          switch (ev.kind) {
            case 'start':
              say({ mark: `budget ${ev.turn_budget} turns` }); break
            case 'thinking':
              setStatus(`Evaluating Group ${gi + 1}/${groups.length} · Turn ${ev.turn}/${ev.of}`)
              say({ turn: ev.turn, call: 'thinking', ticking: Date.now() }); break
            case 'tool':
              say({ turn: ev.turn, call: ev.name, args: ev.args }); break
            case 'observation':
              say({ mark: `↳ ${ev.chars.toLocaleString()} chars returned` }); break
            case 'reasoning':
              say({ think: ev.text }); break
            case 'validating':
              setStatus('Grounding & validating figures against filing text')
              say({ mark: 'checking cited figures against source content', tone: 'supported' })
              break
            case 'verdict': {
              const v = ev.verdict
              seen++
              setVerdicts(vs => [...vs, v])
              say({ mark: `${v.status} — ${v.text.slice(0, 40)}…`, tone: v.rejected ? 'none' : 'supported' })
              break
            }
          }
        }
      } catch (e) {
        say({ mark: `group failed · ${String(e).slice(0, 80)}`, tone: 'contradicted' })
      }
    }

    if (seen !== claims.length)
      say({ mark: `${claims.length - seen} claim(s) returned no verdict`, tone: 'contradicted' })
    setStatus(`${seen}/${claims.length} verdicts completed`); setPhase('done')
  }

  const filteredVerdicts = verdicts.filter(v => {
    if (filter === 'all') return true
    if (filter === 'CONTRADICTED') return v.status === 'CONTRADICTED' || v.status === 'RUN_FAILED'
    return v.status === filter
  })

  return (
    <div className="wrap">
      <header>
        <h1>ClaimCheck</h1>
        <span className="ref">W/P REF B-1 · deck vs data room</span>
        <span className={`ref${live ? ' live' : ''}`}>
          {live ? 'backend connected · live run' : 'no backend'}
        </span>
        <span className="spacer" />
        <a className="archlink" href="/architecture.html">
          Architecture <ArrowRight size={13} className="icon-inline" />
        </a>
        <button className="run" onClick={doExtract} disabled={phase === 'extracting' || !live}>
          <span>1</span>{phase === 'extracting' ? 'Extracting…' : claims.length ? 'Extracted' : 'Extract claims'}
        </button>
        <button className="run" onClick={doVerify} disabled={!claims.length || phase === 'verifying'}>
          <span>2</span>{phase === 'verifying' ? 'Verifying…' : 'Verify claims'}
        </button>
      </header>
      <div className="underrule" />

      {error && <div className="error-banner">{error}</div>}

      <div className="legend-bar">
        <div className="legend-item"><CheckCircle2 size={15} className="icon-supported" /> <span>Traced to Source</span></div>
        <div className="legend-item"><XCircle size={15} className="icon-contradicted" /> <span>Exception (Mismatch)</span></div>
        <div className="legend-item"><AlertTriangle size={15} className="icon-basis" /> <span>Basis Mismatch (Accounting Difference)</span></div>
        <div className="legend-item"><HelpCircle size={15} className="icon-none" /> <span>Not Located / Unverified</span></div>
      </div>

      <ActiveSpotlight phase={phase} status={status} verdicts={verdicts} claimsCount={claims.length} />

      <section className="section-block">
        <div className="section-title">
          <Layers size={16} /> <span>1. Documents & Evidence Corpus</span>
        </div>
        <div className="docs-cols">
          <DocList
            title="Pitch Deck (Assertion)"
            docs={deck}
            role="deck"
            live={live}
            busy={busy}
            uploadProgress={uploadProgress}
            onUpload={f => doUpload('deck', f)}
            onFetch={doFetch}
            onRemove={doRemove}
          />
          <DocList
            title="Data Room Filings (Evidence)"
            docs={room}
            role="room"
            live={live}
            busy={busy}
            uploadProgress={uploadProgress}
            onUpload={f => doUpload('room', f)}
            onFetch={doFetch}
            onRemove={doRemove}
          />
        </div>
      </section>

      <section className="section-block">
        <div className="section-title">
          <Sparkles size={16} /> <span>2. Extracted Assertions from Deck</span>
        </div>
        <ClaimsInspector claims={claims} />
      </section>

      {verdicts.length > 0 && (
        <section className="section-block">
          <div className="section-title">
            <FileCheck2 size={16} /> <span>3. Audit Tally & Summary</span>
          </div>
          <Tally verdicts={verdicts} />

          <div className="filter-toolbar">
            <div className="filter-label">
              <Filter size={14} /> <span>Filter Verdicts:</span>
            </div>
            <button className={`filter-btn ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
              All ({verdicts.length})
            </button>
            <button className={`filter-btn ${filter === 'SUPPORTED' ? 'active' : ''}`} onClick={() => setFilter('SUPPORTED')}>
              Traced ({verdicts.filter(v => v.status === 'SUPPORTED').length})
            </button>
            <button className={`filter-btn ${filter === 'CONTRADICTED' ? 'active' : ''}`} onClick={() => setFilter('CONTRADICTED')}>
              Exceptions ({verdicts.filter(v => v.status === 'CONTRADICTED' || v.status === 'RUN_FAILED').length})
            </button>
            <button className={`filter-btn ${filter === 'BASIS_MISMATCH' ? 'active' : ''}`} onClick={() => setFilter('BASIS_MISMATCH')}>
              Basis Mismatch ({verdicts.filter(v => v.status === 'BASIS_MISMATCH').length})
            </button>
          </div>
        </section>
      )}

      <div className="cols">
        <main className="sheet" aria-live="polite">
          {verdicts.length === 0 ? (
            <div className="empty-sheet">
              <FileCheck2 size={32} className="icon-faint" style={{ margin: '0 auto 10px' }} />
              <div>Audit Workpaper Ready. Click <strong>2. Verify Claims</strong> to generate evidence traces.</div>
            </div>
          ) : (
            filteredVerdicts.map((v, i) => <VerdictRow key={i} v={v} />)
          )}
        </main>
        <Tape lines={lines} />
      </div>

      <footer>
        <b>Agent verifies the claims. Code verifies the evidence.</b>
        <br />
        Retrieval walks each SEC filing's native section tree without chunking, ensuring financial tables retain row labels and fiscal periods. Deterministic Python re-checks all cited figures against raw fetched text to guarantee zero hallucinated citations.
      </footer>
    </div>
  )
}

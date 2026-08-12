/**
 * Typed client for the ClaimCheck backend.
 *
 * The verification endpoint streams: the agent loop takes minutes, so the page
 * must show tool calls as they happen rather than going dark and then dumping
 * a wall of verdicts.
 */

export const API =
  import.meta.env.VITE_API ??
  (location.hostname === 'localhost' || location.hostname === '127.0.0.1'
    ? 'http://127.0.0.1:8000'
    : '')

export type Status =
  | 'SUPPORTED'
  | 'CONTRADICTED'
  | 'BASIS_MISMATCH'
  | 'NO_EVIDENCE'
  | 'NO_SOURCE'
  | 'RUN_FAILED'

export interface Doc {
  doc_id: string
  type: string
  period: string | null
  role: string
}

export interface Claim {
  text: string
  operation: string
  figure: string
  period: string
}

export interface Verdict {
  text: string
  status: Status
  reason?: string
  found?: string
  resolved?: string
  basis?: string
  quote?: string
  cite?: string
  doc_id?: string
  node_ids?: string[]
  /** Set when the validator refused the agent's evidence. */
  rejected?: string
  warnings?: string[]
}

/** Everything the agent loop emits while it works. */
export type Event =
  | { kind: 'start'; claims: number; turn_budget: number }
  | { kind: 'thinking'; turn: number; of: number }
  | { kind: 'tool'; turn: number; name: string; args: string }
  | { kind: 'observation'; turn: number; name: string; chars: number }
  | { kind: 'reasoning'; turn: number; text: string }
  | { kind: 'validating'; turn: number }
  | { kind: 'verdict'; verdict: Verdict }
  | { kind: 'done'; count: number }

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init)
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}${detail ? ` · ${detail.slice(0, 140)}` : ''}`)
  }
  return res.json() as Promise<T>
}

export const health = () => json<{ ok: boolean; live_verify: boolean }>('/health')

export const documents = () => json<Doc[]>('/documents')

export const removeDocument = (doc_id: string) =>
  json<{ ok: boolean; deleted: string }>(`/documents/${encodeURIComponent(doc_id)}`, {
    method: 'DELETE',
  })

export const extract = (doc_id: string) =>
  json<{ claims: Claim[] }>('/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id }),
  })

export async function upload(role: 'deck' | 'room', files: FileList | File[]) {
  if (!files || !files.length) return { documents: [] }
  const body = new FormData()
  body.append('role', role)
  for (const f of Array.from(files)) body.append('files', f)
  return json<{ documents: { name: string; ok: boolean; detail: string }[] }>('/upload', {
    method: 'POST',
    body,
  })
}

export const fetchUrl = (url: string) =>
  json<{ doc_id: string; nodes: number }>('/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })

/**
 * Stream verification. Yields every event the agent emits.
 *
 * SSE frames are separated by a blank line and can split across chunks, so the
 * tail of each read is carried forward rather than parsed as a whole frame.
 */
export async function* verify(claims: Claim[]): AsyncGenerator<Event> {
  const res = await fetch(`${API}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claims }),
  })
  if (!res.ok || !res.body) throw new Error(`verify failed · HTTP ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      const kind = /^event: (.+)$/m.exec(frame)?.[1]
      const data = /^data: (.+)$/m.exec(frame)?.[1]
      if (!kind || !data) continue // keepalive comments have neither
      const parsed = JSON.parse(data)
      yield kind === 'verdict'
        ? ({ kind: 'verdict', verdict: parsed } as Event)
        : ({ kind, ...parsed } as Event)
    }
  }
}

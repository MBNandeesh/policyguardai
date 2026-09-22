/**
 * Frontend logic tests - run with plain Node (no test framework needed):
 *
 *   node frontend/__tests__/logic.test.mjs
 *
 * Covers:
 * 1. Audit-trail scoping: events from report B never display for report A.
 * 2. uploadFile / downloadFile attach the officer Authorization header.
 *
 * TypeScript sources are transpiled on the fly with the TypeScript compiler
 * that ships with the frontend's node_modules.
 */

import { execSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const tsc = path.join(frontendRoot, 'node_modules', '.bin', 'tsc')

// Transpile the lib modules to a temp dir as CommonJS.
const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pg-logic-'))
execSync(
  `"${tsc}" lib/auditScope.ts lib/api.ts --outDir "${outDir}" --module commonjs --target es2019 ` +
    `--esModuleInterop --skipLibCheck --moduleResolution node`,
  { cwd: frontendRoot, stdio: 'pipe' },
)

const { scopeAuditEventsToReport } = await import(
  `file://${path.join(outDir, 'auditScope.js').replace(/\\/g, '/')}`
)
const apiModule = await import(
  `file://${path.join(outDir, 'api.js').replace(/\\/g, '/')}`
)

let failures = 0
function check(name, fn) {
  try {
    fn()
    console.log(`  ok   ${name}`)
  } catch (err) {
    failures++
    console.error(`  FAIL ${name}: ${err.message}`)
  }
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg || 'assertion failed')
}

// ---- localStorage / fetch stubs -------------------------------------------------
const store = new Map()
global.window = {
  localStorage: {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, v),
    removeItem: (k) => store.delete(k),
  },
  URL: { createObjectURL: () => 'blob:fake', revokeObjectURL: () => {} },
}
global.document = {
  createElement: () => ({ click: () => {}, remove: () => {} }),
  body: { appendChild: () => {} },
}

const SESSION = {
  token: 'tok-abc.def',
  officer_id: 'officer-001',
  name: 'Compliance Officer',
  role: 'COMPLIANCE_OFFICER',
  expires_at: new Date(Date.now() + 3600_000).toISOString(),
}
store.set('policyguard.officer.session', JSON.stringify(SESSION))

let lastRequest = null
global.fetch = async (url, init = {}) => {
  lastRequest = { url, init }
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => ({}),
    blob: async () => new Blob(['pdf-bytes'], { type: 'application/pdf' }),
  }
}

// ---- 1. Audit-trail scoping ------------------------------------------------------
console.log('scopeAuditEventsToReport')

const REPORT_A = 'report-aaa'
const REPORT_B = 'report-bbb'
const events = [
  { event_id: 'e1', actor: 'officer-001', action: 'REVIEW_ACCEPT', entity_id: REPORT_A, timestamp: '2026-01-01T00:00:00Z' },
  { event_id: 'e2', actor: 'officer-002', action: 'REVIEW_OVERRIDE', entity_id: REPORT_B, timestamp: '2026-01-02T00:00:00Z' },
  { event_id: 'e3', actor: 'officer-001', action: 'REVIEW_ACCEPT', entity_id: REPORT_A, timestamp: '2026-01-03T00:00:00Z' },
]

check('report A shows only report A events', () => {
  const scoped = scopeAuditEventsToReport(events, REPORT_A)
  assert(scoped.length === 2, `expected 2 events, got ${scoped.length}`)
  assert(scoped.every((e) => e.entity_id === REPORT_A), 'foreign event leaked in')
})

check('report B shows only report B events', () => {
  const scoped = scopeAuditEventsToReport(events, REPORT_B)
  assert(scoped.length === 1, `expected 1 event, got ${scoped.length}`)
  assert(scoped[0].event_id === 'e2', 'wrong event for report B')
})

check('limit is applied after scoping', () => {
  const scoped = scopeAuditEventsToReport(events, REPORT_A, 1)
  assert(scoped.length === 1 && scoped[0].event_id === 'e1', 'limit/slice wrong')
})

check('empty report id yields empty trail', () => {
  assert(scopeAuditEventsToReport(events, '').length === 0, 'should be empty')
})

check('no matching events yields empty trail', () => {
  assert(scopeAuditEventsToReport(events, 'report-unknown').length === 0, 'should be empty')
})

// ---- 2. API auth headers ----------------------------------------------------------
console.log('api client auth headers')

check('uploadFile attaches Authorization header', async () => {
  const file = new File(['x'], 'tender.pdf', { type: 'application/pdf' })
  await apiModule.uploadFile('/documents/upload', file, { document_type: 'tender' })
  const auth = lastRequest.init.headers?.Authorization || lastRequest.init.headers?.authorization
  assert(auth === `Bearer ${SESSION.token}`, `missing/incorrect auth header: ${auth}`)
  assert(lastRequest.init.body instanceof FormData, 'body should be FormData')
  // Content-Type must NOT be set manually for multipart (browser sets boundary).
  const ct = lastRequest.init.headers?.['Content-Type']
  assert(!ct, `Content-Type must not be manually set, got: ${ct}`)
})

check('downloadFile attaches Authorization header and requests right path', async () => {
  await apiModule.downloadFile('/compliance/decision/r-1/download', 'out.pdf')
  const auth = lastRequest.init.headers?.Authorization || lastRequest.init.headers?.authorization
  assert(auth === `Bearer ${SESSION.token}`, `missing/incorrect auth header: ${auth}`)
  assert(lastRequest.url.includes('/compliance/decision/r-1/download'), 'wrong URL')
})

check('apiGet attaches Authorization header when logged in', async () => {
  await apiModule.apiGet('/auth/me')
  const auth = lastRequest.init.headers?.Authorization || lastRequest.init.headers?.authorization
  assert(auth === `Bearer ${SESSION.token}`, `missing/incorrect auth header: ${auth}`)
})

check('requests omit Authorization header when logged out', async () => {
  store.delete('policyguard.officer.session')
  await apiModule.apiGet('/auth/me')
  const auth = lastRequest.init.headers?.Authorization || lastRequest.init.headers?.authorization
  assert(!auth, 'should not send auth header when logged out')
})

// ---- 3. Centralized 401 handling ------------------------------------------------
console.log('centralized 401 handling')

check('401 clears stored session', async () => {
  store.set('policyguard.officer.session', JSON.stringify(SESSION))
  global.fetch = async () => ({
    ok: false,
    status: 401,
    statusText: 'Unauthorized',
    json: async () => ({ detail: 'Session invalid or expired. Please log in again.' }),
  })
  try {
    await apiModule.apiGet('/documents/doc-1')
    assert(false, 'should have thrown ApiError')
  } catch (err) {
    assert(err.status === 401, `expected 401, got ${err.status}`)
  }
  assert(!store.has('policyguard.officer.session'), 'session should be cleared on 401')
})

check('non-401 errors keep the session', async () => {
  store.set('policyguard.officer.session', JSON.stringify(SESSION))
  global.fetch = async () => ({
    ok: false,
    status: 500,
    statusText: 'Internal Server Error',
    json: async () => ({ detail: 'Document processing failed' }),
  })
  try {
    await apiModule.apiGet('/documents/doc-1')
    assert(false, 'should have thrown ApiError')
  } catch (err) {
    assert(err.status === 500, `expected 500, got ${err.status}`)
  }
  assert(store.has('policyguard.officer.session'), 'session must survive non-401 errors')
})

// ---- summary -----------------------------------------------------------------------
console.log(failures === 0 ? '\nAll frontend logic tests passed.' : `\n${failures} test(s) FAILED.`)
fs.rmSync(outDir, { recursive: true, force: true })
process.exit(failures === 0 ? 0 : 1)

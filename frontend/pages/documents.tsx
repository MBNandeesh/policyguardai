import React, { useCallback, useState } from 'react'
import Head from 'next/head'
import Link from 'next/link'
import { Layout } from '../components/Layout'
import { Card, Button, Loading, ErrorMessage, StatusBadge, DocumentTypeBadge } from '../components/UI'
import { uploadFile, ApiError } from '../lib/api'
import { DocumentRecord } from '../lib/types'
import { formatDate, formatFileSize, COLORS } from '../lib/utils'

type SlotKey = 'tender' | 'bidder'

const SLOTS: Record<SlotKey, {
  title: string
  icon: string
  description: string
  accent: string
  acceptMultiple: boolean
}> = {
  tender: {
    title: 'Tender Document',
    icon: '📑',
    description: 'The NIT / RFP that states the requirements. Requirements are extracted from this PDF.',
    accent: COLORS.blue,
    acceptMultiple: false,
  },
  bidder: {
    title: 'Bidder Document(s)',
    icon: '📨',
    description: 'The bid submission containing the bidder\'s evidence. Mapped against the tender requirements.',
    accent: COLORS.success,
    acceptMultiple: true,
  },
}

interface SlotState {
  uploading: boolean
  progress: number
  error: string | null
  docs: DocumentRecord[]
}

const EMPTY_SLOT: SlotState = { uploading: false, progress: 0, error: null, docs: [] }

export default function Documents() {
  const [slots, setSlots] = useState<Record<SlotKey, SlotState>>({ tender: EMPTY_SLOT, bidder: EMPTY_SLOT })
  const [dragSlot, setDragSlot] = useState<SlotKey | null>(null)

  const updateSlot = useCallback((slot: SlotKey, patch: Partial<SlotState>) => {
    setSlots((prev) => ({ ...prev, [slot]: { ...prev[slot], ...patch } }))
  }, [])

  async function handleFile(slot: SlotKey, file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      updateSlot(slot, { error: 'Please upload a PDF file' })
      return
    }
    if (file.size > 200 * 1024 * 1024) {
      updateSlot(slot, { error: 'File size exceeds 200MB limit' })
      return
    }

    let progressInterval: ReturnType<typeof setInterval> | undefined
    try {
      updateSlot(slot, { uploading: true, error: null, progress: 0 })

      progressInterval = setInterval(() => {
        setSlots((prev) => ({
          ...prev,
          [slot]: { ...prev[slot], progress: Math.min(prev[slot].progress + 10, 90) },
        }))
      }, 200)

      const result = await uploadFile<DocumentRecord>('/documents/upload', file, { document_type: slot })

      clearInterval(progressInterval)
      updateSlot(slot, { progress: 100, docs: [result, ...slots[slot].docs] })

      setTimeout(() => {
        updateSlot(slot, { uploading: false, progress: 0 })
      }, 800)
    } catch (err) {
      if (progressInterval) clearInterval(progressInterval)
      updateSlot(slot, {
        uploading: false,
        progress: 0,
        error: err instanceof ApiError ? `Upload failed: ${err.detail}` : `Upload failed: ${err instanceof Error ? err.message : 'Unknown error'}`,
      })
    }
  }

  function removeDoc(slot: SlotKey, documentId: string) {
    updateSlot(slot, { docs: slots[slot].docs.filter((d) => d.document_id !== documentId) })
  }

  function makeDropHandlers(slot: SlotKey) {
    return {
      onDragEnter: (e: React.DragEvent) => { e.preventDefault(); setDragSlot(slot) },
      onDragLeave: (e: React.DragEvent) => { e.preventDefault(); setDragSlot(null) },
      onDragOver: (e: React.DragEvent) => { e.preventDefault(); setDragSlot(slot) },
      onDrop: (e: React.DragEvent) => {
        e.preventDefault()
        setDragSlot(null)
        const files = Array.from(e.dataTransfer.files || [])
        if (files.length > 0) handleFile(slot, files[0])
      },
    }
  }

  const tenderDocs = slots.tender.docs
  const bidderDocs = slots.bidder.docs
  const readyTender = tenderDocs.filter((d) => d.processing_status === 'processed')
  const readyBidders = bidderDocs.filter((d) => d.processing_status === 'processed')

  function renderDropZone(slot: SlotKey) {
    const cfg = SLOTS[slot]
    const state = slots[slot]
    const active = dragSlot === slot
    return (
      <div
        key={slot}
        style={{
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: COLORS.cardBg,
          border: `1px solid ${active ? cfg.accent : COLORS.border}`,
          borderRadius: '12px',
          overflow: 'hidden',
          boxShadow: active ? `0 0 0 3px ${cfg.accent}25` : '0 1px 3px rgba(16,24,40,0.06)',
          transition: 'all 0.2s',
        }}
      >
        {/* Zone header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            padding: '0.9rem 1.25rem',
            borderBottom: `1px solid ${COLORS.border}`,
            background: cfg.accent + '08',
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '34px',
              height: '34px',
              borderRadius: '9px',
              backgroundColor: cfg.accent + '18',
              fontSize: '1rem',
            }}
          >
            {cfg.icon}
          </span>
          <div style={{ flex: 1 }}>
            <p style={{ margin: 0, fontWeight: 600, color: COLORS.textMain, fontSize: '0.95rem' }}>{cfg.title}</p>
            <p style={{ margin: 0, fontSize: '0.75rem', color: COLORS.textSecondary }}>{cfg.description}</p>
          </div>
        </div>

        <div style={{ padding: '1.25rem' }}>
          <input
            type="file"
            accept=".pdf"
            disabled={state.uploading}
            style={{ display: 'none' }}
            id={`fileInput-${slot}`}
            onChange={(e) => {
              const files = e.target.files
              if (files && files.length > 0) handleFile(slot, files[0])
              e.target.value = ''
            }}
          />
          <label
            htmlFor={`fileInput-${slot}`}
            {...makeDropHandlers(slot)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.4rem',
              padding: '2.25rem 1rem',
              border: `2px dashed ${active ? cfg.accent : COLORS.border}`,
              borderRadius: '10px',
              backgroundColor: active ? cfg.accent + '0A' : 'transparent',
              textAlign: 'center',
              cursor: state.uploading ? 'wait' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {state.uploading ? (
              <>
                <div style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>📤</div>
                <p style={{ margin: 0, color: COLORS.textMain, fontWeight: 500, fontSize: '0.9rem' }}>
                  Uploading &amp; processing…
                </p>
                <div
                  style={{
                    width: '100%',
                    maxWidth: '260px',
                    height: '7px',
                    backgroundColor: COLORS.bgLight,
                    borderRadius: '4px',
                    overflow: 'hidden',
                    marginTop: '0.4rem',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      backgroundColor: cfg.accent,
                      width: `${state.progress}%`,
                      transition: 'width 0.3s',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <p style={{ margin: 0, fontSize: '0.78rem', color: COLORS.textSecondary }}>{state.progress}%</p>
              </>
            ) : (
              <>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '52px',
                    height: '52px',
                    borderRadius: '14px',
                    backgroundColor: cfg.accent + '12',
                    fontSize: '1.6rem',
                    marginBottom: '0.25rem',
                  }}
                >
                  ⬆️
                </span>
                <p style={{ margin: 0, color: COLORS.textMain, fontWeight: 600, fontSize: '0.92rem' }}>
                  Drop PDF here or click to browse
                </p>
                <p style={{ margin: 0, fontSize: '0.78rem', color: COLORS.textSecondary }}>
                  PDF only · up to 200 MB
                </p>
              </>
            )}
          </label>

          {state.error && (
            <div style={{ marginTop: '0.85rem' }}>
              <ErrorMessage message={state.error} />
            </div>
          )}

          {/* Uploaded docs in this slot */}
          {state.docs.length > 0 && (
            <div style={{ marginTop: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {state.docs.map((doc) => (
                <div
                  key={doc.document_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.65rem 0.85rem',
                    backgroundColor: COLORS.bgLight,
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: '8px',
                  }}
                >
                  <span style={{ fontSize: '1.1rem' }}>📄</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 500, color: COLORS.textMain, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {doc.filename}
                    </p>
                    <p style={{ margin: 0, fontSize: '0.72rem', color: COLORS.textSecondary }}>
                      {formatFileSize(doc.file_size)} · {doc.page_count} page{doc.page_count !== 1 ? 's' : ''} · {formatDate(doc.upload_time)}
                    </p>
                  </div>
                  <StatusBadge status={doc.processing_status as any} size="sm" />
                  <button
                    onClick={() => removeDoc(slot, doc.document_id)}
                    aria-label={`Remove ${doc.filename}`}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: COLORS.textSecondary,
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                      padding: '0.25rem',
                    }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <Layout>
      <Head>
        <title>Documents - PolicyGuard AI</title>
      </Head>

      <div>
        <div style={{ marginBottom: '1.75rem' }}>
          <h1 style={{ margin: '0 0 0.5rem 0', fontSize: '1.65rem', fontWeight: 700, color: COLORS.textMain }}>Documents</h1>
          <p style={{ margin: 0, color: COLORS.textSecondary, fontSize: '0.95rem' }}>
            Upload <strong>both</strong> the tender and the bidder PDF. PolicyGuard maps the tender
            requirements onto the bidder&apos;s submitted evidence for a paired compliance assessment.
          </p>
        </div>

        {/* Dual upload zones */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
          {renderDropZone('tender')}
          {renderDropZone('bidder')}
        </div>

        {/* Analyze CTA */}
        {(tenderDocs.length > 0 || bidderDocs.length > 0) && (
          <div
            style={{
              marginTop: '1.5rem',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              padding: '1.1rem 1.4rem',
              backgroundColor: COLORS.cardBg,
              border: `1px solid ${COLORS.border}`,
              borderRadius: '12px',
              boxShadow: '0 1px 3px rgba(16,24,40,0.06)',
            }}
          >
            <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1rem' }}>📑</span>
                <span style={{ fontSize: '0.88rem', color: COLORS.textMain }}>
                  {tenderDocs.length} tender document{tenderDocs.length !== 1 ? 's' : ''}
                  {readyTender.length !== tenderDocs.length && (
                    <span style={{ color: COLORS.textSecondary }}> ({readyTender.length} ready)</span>
                  )}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1rem' }}>📨</span>
                <span style={{ fontSize: '0.88rem', color: COLORS.textMain }}>
                  {bidderDocs.length} bidder document{bidderDocs.length !== 1 ? 's' : ''}
                  {readyBidders.length !== bidderDocs.length && (
                    <span style={{ color: COLORS.textSecondary }}> ({readyBidders.length} ready)</span>
                  )}
                </span>
              </div>
            </div>
            <Link
              href={
                readyTender.length > 0
                  ? `/compliance?tender_document_id=${readyTender[0].document_id}${readyBidders.map((d) => `&bidder_document_ids=${d.document_id}`).join('')}`
                  : '/compliance'
              }
            >
              <Button disabled={readyTender.length === 0} style={{ padding: '0.7rem 1.4rem', fontWeight: 600 }}>
                {readyBidders.length > 0 ? '⚖️ Run Paired Compliance Analysis' : 'Analyze Tender Only →'}
              </Button>
            </Link>
          </div>
        )}

        {/* How it works */}
        <div style={{ marginTop: '1.75rem' }}>
          <Card title="How paired analysis works" subtitle="Three steps from upload to decision report">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              {[
                { n: '1', icon: '📑', text: 'Upload the tender (NIT/RFP). Requirements are extracted from it.' },
                { n: '2', icon: '📨', text: 'Upload the bidder PDF(s) containing the submitted evidence.' },
                { n: '3', icon: '⚖️', text: 'Each tender requirement is mapped to evidence from both PDFs, evaluated with regulatory grounding, risk and a review queue.' },
              ].map((step) => (
                <div
                  key={step.n}
                  style={{
                    display: 'flex',
                    gap: '0.75rem',
                    padding: '1rem',
                    backgroundColor: COLORS.bgLight,
                    borderRadius: '10px',
                    border: `1px solid ${COLORS.border}`,
                  }}
                >
                  <span
                    style={{
                      flexShrink: 0,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '30px',
                      height: '30px',
                      borderRadius: '50%',
                      backgroundColor: COLORS.navy,
                      color: 'white',
                      fontWeight: 700,
                      fontSize: '0.85rem',
                    }}
                  >
                    {step.n}
                  </span>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: COLORS.textMain, lineHeight: 1.55 }}>
                    <span style={{ marginRight: '0.35rem' }}>{step.icon}</span>
                    {step.text}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Empty state */}
        {tenderDocs.length === 0 && bidderDocs.length === 0 && (
          <div style={{ marginTop: '1.5rem' }}>
            <Card>
              <div style={{ textAlign: 'center', padding: '1.5rem', color: COLORS.textSecondary }}>
                <p style={{ fontSize: '0.9rem', margin: 0 }}>
                  No documents uploaded yet. Start with the tender PDF above, then add the bidder&apos;s submission.
                </p>
              </div>
            </Card>
          </div>
        )}
      </div>
    </Layout>
  )
}

import React, { useState } from 'react'
import Head from 'next/head'
import Link from 'next/link'
import { Layout } from '../components/Layout'
import { Card, Button, Loading, ErrorMessage, StatusBadge } from '../components/UI'
import { uploadFile, ApiError } from '../lib/api'
import { DocumentRecord } from '../lib/types'
import { formatDate, formatFileSize, COLORS } from '../lib/utils'

export default function Documents() {
  const [files, setFiles] = useState<DocumentRecord[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragActive, setDragActive] = useState(false)

  function handleDrag(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(e.type === 'dragenter' || e.type === 'dragover')
  }

  async function handleFiles(fileList: FileList) {
    const file = fileList[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Please upload a PDF file')
      return
    }

    if (file.size > 50 * 1024 * 1024) {
      setUploadError('File size exceeds 50MB limit')
      return
    }

    let progressInterval: ReturnType<typeof setInterval> | undefined
    try {
      setUploading(true)
      setUploadError(null)
      setUploadProgress(0)

      // Simulate progress
      progressInterval = setInterval(() => {
        setUploadProgress((p) => (p < 90 ? p + 10 : p))
      }, 200)

      const result = await uploadFile<DocumentRecord>('/documents/upload', file)

      clearInterval(progressInterval)
      setUploadProgress(100)

      // Add to list
      setFiles((prev) => [result, ...prev])

      // Reset after success
      setTimeout(() => {
        setUploadProgress(0)
        setUploading(false)
      }, 1000)
    } catch (err) {
      if (progressInterval) clearInterval(progressInterval)
      setUploading(false)
      setUploadProgress(0)
      if (err instanceof ApiError) {
        setUploadError(`Upload failed: ${err.detail}`)
      } else {
        setUploadError(`Upload failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
      }
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files) {
      handleFiles(e.dataTransfer.files)
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      handleFiles(e.target.files)
    }
  }

  return (
    <Layout>
      <Head>
        <title>Documents - PolicyGuard AI</title>
      </Head>

      <div>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain }}>Documents</h1>
          <p style={{ margin: 0, color: COLORS.textSecondary }}>
            Upload tender PDFs for compliance assessment and analysis.
          </p>
        </div>

        {/* Upload Area */}
        <Card title="Upload Tender PDF" subtitle="Drag and drop or select a file">
          <input
            type="file"
            accept=".pdf"
            onChange={handleChange}
            disabled={uploading}
            style={{ display: 'none' }}
            id="fileInput"
          />

          <label
            htmlFor="fileInput"
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            style={{
              display: 'block',
              padding: '3rem',
              border: `2px dashed ${dragActive ? COLORS.navy : COLORS.border}`,
              borderRadius: '6px',
              backgroundColor: dragActive ? COLORS.bgLight : 'transparent',
              textAlign: 'center',
              cursor: uploading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {uploading ? (
              <>
                <div
                  style={{
                    fontSize: '2rem',
                    marginBottom: '1rem',
                  }}
                >
                  📤
                </div>
                <p style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain }}>
                  Uploading and analyzing...
                </p>
                <div
                  style={{
                    width: '100%',
                    maxWidth: '300px',
                    height: '8px',
                    backgroundColor: COLORS.bgLight,
                    borderRadius: '4px',
                    margin: '1rem auto',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      backgroundColor: COLORS.blue,
                      width: `${uploadProgress}%`,
                      transition: 'width 0.3s',
                    }}
                  />
                </div>
                <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.textSecondary }}>
                  {uploadProgress}%
                </p>
              </>
            ) : (
              <>
                <div
                  style={{
                    fontSize: '3rem',
                    marginBottom: '1rem',
                  }}
                >
                  📄
                </div>
                <p style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain, fontWeight: 500 }}>
                  Drag PDF here or click to select
                </p>
                <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.textSecondary }}>
                  PDF files only, up to 50 MB
                </p>
              </>
            )}
          </label>

          {uploadError && (
            <div style={{ marginTop: '1rem' }}>
              <ErrorMessage message={uploadError} />
            </div>
          )}
        </Card>

        {/* Documents List */}
        {files.length > 0 && (
          <div style={{ marginTop: '2rem' }}>
          <Card title="Uploaded Documents" subtitle={`${files.length} document${files.length !== 1 ? 's' : ''}`}>
            <div style={{ overflowX: 'auto' }}>
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '0.875rem',
                }}
              >
                <thead>
                  <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    <th
                      style={{
                        padding: '0.75rem',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: COLORS.textMain,
                      }}
                    >
                      File Name
                    </th>
                    <th
                      style={{
                        padding: '0.75rem',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: COLORS.textMain,
                      }}
                    >
                      Size
                    </th>
                    <th
                      style={{
                        padding: '0.75rem',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: COLORS.textMain,
                      }}
                    >
                      Pages
                    </th>
                    <th
                      style={{
                        padding: '0.75rem',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: COLORS.textMain,
                      }}
                    >
                      Uploaded
                    </th>
                    <th
                      style={{
                        padding: '0.75rem',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: COLORS.textMain,
                      }}
                    >
                      Status
                    </th>
                    <th
                      style={{
                        padding: '0.75rem',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: COLORS.textMain,
                      }}
                    >
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr key={file.document_id} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                      <td style={{ padding: '0.75rem', color: COLORS.textMain }}>
                        {file.filename}
                      </td>
                      <td style={{ padding: '0.75rem', color: COLORS.textSecondary }}>
                        {formatFileSize(file.file_size)}
                      </td>
                      <td style={{ padding: '0.75rem', color: COLORS.textSecondary }}>
                        {file.page_count}
                      </td>
                      <td style={{ padding: '0.75rem', color: COLORS.textSecondary }}>
                        {formatDate(file.upload_time)}
                      </td>
                      <td style={{ padding: '0.75rem' }}>
                        <StatusBadge status={file.processing_status as any} size="sm" />
                      </td>
                      <td style={{ padding: '0.75rem' }}>
                        <Link href={`/compliance?document_id=${file.document_id}`}>
                          <Button style={{ cursor: 'pointer', fontSize: '0.75rem' }}>
                            Review
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          </div>
        )}

        {/* Empty State */}
        {files.length === 0 && !uploading && (
          <div style={{ marginTop: '2rem' }}>
          <Card>
            <div style={{ textAlign: 'center', padding: '2rem', color: COLORS.textSecondary }}>
              <p style={{ fontSize: '0.875rem' }}>No documents uploaded yet.</p>
              <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>
                Start by uploading a tender PDF above to begin compliance assessment.
              </p>
            </div>
          </Card>
          </div>
        )}
      </div>
    </Layout>
  )
}

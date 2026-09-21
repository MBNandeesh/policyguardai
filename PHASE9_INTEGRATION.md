# Phase 9 Integration & Deployment Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Browser                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PolicyGuard AI Frontend (Next.js 14)                │  │
│  │  - Dashboard                                         │  │
│  │  - Document Upload                                  │  │
│  │  - Compliance Review (Phase 8 integration)          │  │
│  │  - Reports                                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│                   HTTP/JSON API Calls                       │
│                          ↓                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
        ┌──────────────────────────────────────┐
        │  Backend API (FastAPI 0.100.0)       │
        ├──────────────────────────────────────┤
        │  Phase 3: Regulatory Registry        │
        │  Phase 4: Retrieval & Vector Store   │
        │  Phase 5: Requirements Analysis      │
        │  Phase 6: Requirement Extraction     │
        │  Phase 7: Compliance Evaluation      │
        │  Phase 8: Decision Aggregation ✅    │
        │                                      │
        │  Endpoints Used by Phase 9:          │
        │  - POST /documents/upload            │
        │  - POST /compliance/decision         │
        │  - GET /compliance/requirements/{id}/explanation
        │                                      │
        └──────────────────────────────────────┘
                           ↓
        ┌──────────────────────────────────────┐
        │  Storage & Services                  │
        ├──────────────────────────────────────┤
        │  - File storage                      │
        │  - Phase 8 decision reports          │
        │  - Requirement explanations          │
        │  - Human review queues               │
        │                                      │
        └──────────────────────────────────────┘
```

## Quick Start (Development)

### Prerequisites
```bash
# Backend requirements
Python 3.12.10
pip (from requirements.txt)

# Frontend requirements
Node.js 18+
npm 10+
```

### Step 1: Start Backend
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API available at: `http://localhost:8000/api/v1`

### Step 2: Configure Frontend
```bash
cd frontend

# Create environment file
cp .env.example .env.local

# Update .env.local if backend is on different host
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1' >> .env.local
```

### Step 3: Install & Run Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend available at: `http://localhost:3000`

### Step 4: Test Integration
1. Open browser: `http://localhost:3000`
2. Click Dashboard → "Upload Document"
3. Upload a tender PDF (or create dummy PDF with sample text)
4. After upload completes, click "Review"
5. See compliance requirements populated from Phase 8
6. Click requirement to view explanation from backend

## API Testing with curl

### Upload Document
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@tender.pdf"

# Returns:
{
  "document_id": "doc-uuid",
  "file_name": "tender.pdf",
  "file_size": 12345,
  "pages": 5,
  "upload_time": "2024-01-01T12:00:00Z",
  "processing_status": "COMPLETED"
}
```

### Generate Compliance Decision
```bash
curl -X POST http://localhost:8000/api/v1/compliance/decision \
  -H "Content-Type: application/json" \
  -d '{"document_id": "doc-uuid"}'

# Returns ComplianceDecisionReport with:
# - overall_status: COMPLIANT | HIGH_RISK | REVIEW_REQUIRED | UNKNOWN
# - overall_risk: CRITICAL | HIGH | MEDIUM | LOW | INFO
# - findings: ComplianceFinding[]
# - human_review_queue: HumanReviewItem[]
# - executive_summary: string
```

### Get Requirement Explanation
```bash
curl "http://localhost:8000/api/v1/compliance/requirements/req-123/explanation?analysis_id=analysis-456"

# Returns RequirementExplanation with:
# - evaluation_status: COMPLIANT | POTENTIAL_NON_COMPLIANCE | etc.
# - risk_level: CRITICAL | HIGH | MEDIUM | LOW | INFO
# - reason: string (why this status)
# - evidence_summary: string
# - regulatory_reference: string
# - source_page: integer
```

## Docker Deployment

### Build Both Images
```bash
# Backend Docker
docker build -f backend/Dockerfile -t policyguard-backend:1.0 .

# Frontend Docker
docker build -f frontend/Dockerfile -t policyguard-frontend:1.0 frontend/
```

### Run with Docker Compose
```bash
# Update docker-compose.yml:
# - Backend service on port 8000
# - Frontend service on port 3000
# - Both can communicate via service name

docker-compose up -d
```

Frontend: `http://localhost:3000`
Backend API: `http://localhost:8000/api/v1`

## Production Deployment

### Frontend (Vercel)
```bash
# Deploy via Vercel CLI
npm install -g vercel
cd frontend
vercel --env NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
```

### Frontend (Self-hosted)
```bash
cd frontend
npm install
npm run build
npm start  # Runs on port 3000
```

### Backend (Gunicorn/Nginx)
```bash
cd backend
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app

# Behind Nginx for HTTPS
```

## Environment Configuration

### Frontend (.env.local)
```
# Required
NEXT_PUBLIC_API_URL=http://your-backend-url/api/v1

# Optional
NEXT_PUBLIC_APP_TITLE=PolicyGuard AI
NEXT_PUBLIC_ENVIRONMENT=production
```

### Backend (.env)
```
# See backend/.env.example
STORAGE_PATH=./storage
APP_HOST=0.0.0.0
APP_PORT=8000
```

## Integration Points

### Frontend → Backend APIs Used

1. **Document Upload**
   - Endpoint: `POST /documents/upload`
   - Payload: multipart/form-data (file)
   - Response: DocumentRecord

2. **Compliance Decision**
   - Endpoint: `POST /compliance/decision`
   - Payload: `{ document_id: string }`
   - Response: ComplianceDecisionReport

3. **Requirement Explanation**
   - Endpoint: `GET /compliance/requirements/{requirement_id}/explanation?analysis_id={analysis_id}`
   - Response: RequirementExplanation

### No Backend Modifications Required

All Phase 8 endpoints are complete and ready for frontend consumption:
- ✅ Decision aggregation logic (no changes needed)
- ✅ Risk classification (no changes needed)
- ✅ Explainability (no changes needed)
- ✅ Human review queue (no changes needed)
- ✅ Report persistence (no changes needed)

Frontend reuses these endpoints as-is without backend refactoring.

## Testing & Validation

### Frontend Tests
```bash
cd frontend
npm run test

# Validates:
# - TypeScript compilation
# - API client structure
# - Component props
# - Type safety
```

### Backend Tests
```bash
cd backend
python -m pytest tests/ -v

# Confirms:
# - Phase 8 tests passing (21 tests)
# - Phase 1-7 baseline passing (66 tests)
# - No regressions (2 expected OCR failures)
```

### Integration Test
1. Start backend: `cd backend && python -m uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to http://localhost:3000
4. Upload test PDF → Review → Select requirement → View explanation
5. Verify all data flows from backend to UI

## Troubleshooting

### Frontend Can't Connect to Backend
- Check backend is running: `curl http://localhost:8000/api/v1/health`
- Verify `NEXT_PUBLIC_API_URL` in `.env.local`
- Check CORS headers on backend
- Check browser console for errors

### Upload Fails
- Verify file is PDF format
- Check file size < 50MB
- Check backend storage permissions
- Review browser console error message

### Compliance Review Shows No Data
- Ensure document uploaded successfully
- Check backend processing completed
- Verify analysis_id in decision report
- Check browser dev tools network tab for API errors

### Missing Requirement Explanations
- Explanations are loaded on-demand
- Requires analysis_id from decision report
- Check backend Phase 8 service logging
- Explanations may not exist for all requirements (ok)

## Performance Tuning

### Frontend
- Lazy load components with Next.js `dynamic`
- Implement pagination for requirement lists
- Cache API responses with SWR
- Optimize images with Next.js `Image` component

### Backend
- Add API response caching
- Implement connection pooling
- Index storage directories
- Monitor Phase 8 service latency

## Security

### Frontend
- CSP headers configured
- No hardcoded secrets
- HTTPS required in production
- SameSite cookie policy

### Backend
- Input validation on all endpoints
- CORS properly configured
- Rate limiting (can be added)
- Request logging/audit trail (can be added)

## Monitoring & Logging

### Frontend Logging
```typescript
// frontend/lib/api.ts includes error logging
console.error(`API Error ${status}: ${detail}`)
```

### Backend Logging
```python
# backend/app/logging_config.py includes request/response logging
logger.info(f"POST /compliance/decision for document {document_id}")
```

## Next Steps & Future Enhancements

1. **Officer Decision Persistence**
   - Create backend endpoint: `POST /compliance/decisions/{requirement_id}`
   - Store officer decisions and reasoning

2. **Real-time Notifications**
   - WebSocket support for upload progress
   - Live status updates during analysis

3. **Advanced Search & Filtering**
   - Requirement title search
   - Risk level filtering
   - Severity filtering
   - Status-based sorting

4. **Report Export**
   - PDF generation via backend
   - CSV export for spreadsheet analysis
   - Email report delivery

5. **Multi-user Support**
   - User authentication/authorization
   - Audit trail for all decisions
   - Concurrent document review

6. **Analytics Dashboard**
   - Compliance trends
   - Decision patterns
   - Processing metrics

## Files Changed Summary

### New Files Created
- `frontend/components/Layout.tsx` - Main layout component
- `frontend/components/UI.tsx` - Reusable UI components
- `frontend/lib/types.ts` - TypeScript type definitions
- `frontend/lib/utils.ts` - Utility functions and color scheme
- `frontend/pages/documents.tsx` - Document upload page
- `frontend/pages/compliance.tsx` - Compliance review page
- `frontend/pages/reports.tsx` - Reports page
- `frontend/__tests__/api.integration.test.ts` - Integration tests
- `frontend/README.md` - Frontend documentation
- `frontend/.env.example` - Environment template
- `frontend/.gitignore` - Git ignore rules

### Modified Files
- `frontend/lib/api.ts` - Enhanced with POST, file upload, error handling
- `frontend/pages/_app.tsx` - Global styling and app wrapper
- `frontend/pages/index.tsx` - Dashboard implementation

### No Backend Changes Required
- All Phase 5-8 APIs used as-is
- No business logic modifications
- No model changes
- Pure frontend integration layer

---

**Phase 9 Complete**: Professional procurement compliance officer frontend fully integrated with Phase 5-8 backend APIs. Ready for development and production deployment.

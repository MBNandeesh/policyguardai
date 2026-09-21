# PolicyGuard AI - Phase 9 Frontend

## Overview

Phase 9 implements a professional government-grade procurement compliance officer frontend for PolicyGuard AI. The frontend provides a complete UI for uploading tender PDFs, reviewing compliance assessments, and managing compliance decisions.

## Technology Stack

- **Framework**: Next.js 14.0.0 with React 18.2.0
- **Language**: TypeScript 5.6.2
- **Styling**: Tailwind CSS 4.0.0 + inline styles for fine control
- **Build Tool**: Next.js built-in

## Project Structure

```
frontend/
├── components/
│   ├── Layout.tsx          # Main layout with header, sidebar, footer
│   └── UI.tsx              # Reusable UI components (badges, buttons, cards, etc.)
├── lib/
│   ├── api.ts              # API client with POST/GET/file upload
│   ├── types.ts            # TypeScript types for backend models
│   └── utils.ts            # Color scheme, formatting utilities
├── pages/
│   ├── _app.tsx            # Next.js app wrapper
│   ├── index.tsx           # Dashboard
│   ├── documents.tsx       # Document upload and management
│   ├── compliance.tsx      # Compliance review (main review screen)
│   └── reports.tsx         # Compliance reports
├── __tests__/
│   └── api.integration.test.ts  # API integration tests
├── styles/
│   └── globals.css         # Global CSS
├── package.json            # Dependencies
├── tsconfig.json           # TypeScript config
└── next.config.js          # Next.js config
```

## Pages

### 1. Dashboard (`/`)
- Summary KPI cards (documents reviewed, requirements checked, high risk, pending)
- Quick action buttons (upload, review, reports)
- Getting started guide
- System status

### 2. Documents (`/documents`)
- PDF upload with drag-and-drop
- File validation (PDF only, 50MB max)
- Upload progress indicator
- Document list with metadata
- Quick link to compliance review for each document

### 3. Compliance Review (`/compliance`)
**Most Important Screen**

Two-column layout:
- **Left Column**: 
  - Overall compliance summary
  - Status filters (All, Compliant, Review Required, Non-Compliant)
  - Requirements list with status and risk badges
  - Clickable to select requirement
  
- **Right Column**:
  - Requirement title and ID
  - Status and risk badges
  - Full evaluation explanation from backend
  - Evidence summary
  - Regulatory reference (if available)
  - Source document page number (if available)
  - Officer decision controls (Accept, Flag, Reject)
  - Reason field for officer decision

### 4. Reports (`/reports`)
- List of compliance reports
- Report detail view
- Statistics (requirements, compliant, review required, non-compliant)
- Executive summary and key findings
- Export/print actions (UI ready, backend integration pending)

## API Integration

The frontend integrates with existing Phase 5-8 backend APIs:

### Document Upload
```
POST /documents/upload
Body: multipart/form-data with file
Response: DocumentRecord { document_id, file_name, pages, ... }
```

### Compliance Decision
```
POST /compliance/decision
Body: { document_id: string }
Response: ComplianceDecisionReport { overall_status, overall_risk, findings, ... }
```

### Requirement Explanation
```
GET /compliance/requirements/{requirement_id}/explanation?analysis_id={analysis_id}
Response: RequirementExplanation { reason, evidence_summary, regulatory_reference, ... }
```

All APIs called through enhanced API client in `lib/api.ts` with:
- Error handling and type safety
- FormData for file uploads
- JSON serialization for POST bodies
- Proper HTTP status code handling

## Color Scheme

Professional government-service styling:
- **Primary Navy**: #163A5F
- **Secondary Blue**: #2F5D8C
- **Background**: #F7F8FA
- **Cards**: #FFFFFF
- **Text**: #263238 (main), #667085 (secondary)
- **Borders**: #D9DEE5
- **Success**: #2E7D5B (green)
- **Warning**: #B7791F (amber)
- **Error**: #B54747 (red)

Status communication via text + optional icon (not color alone).

## Component Library

### UI Components (UI.tsx)
- `StatusBadge`: Displays FindingStatus or OverallComplianceStatus
- `RiskBadge`: Displays RiskLevel
- `Card`: Container component with optional title/subtitle
- `KPICard`: Metric display card
- `Button`: Primary/secondary/danger variants
- `Loading`: Spinner with text
- `ErrorMessage`: Error display with retry

### Layout Component (Layout.tsx)
- Header with PolicyGuard AI branding
- Responsive sidebar navigation
- Main content area
- Footer with compliance disclaimer

## Setup & Development

### Prerequisites
- Node.js 18+
- npm or yarn

### Installation
```bash
cd frontend
npm install
```

### Development Server
```bash
npm run dev
```
Runs on http://localhost:3000

### Type Checking
```bash
npx tsc --noEmit
```

### Build
```bash
npm run build
npm start
```

## API Client Usage

### GET Request
```typescript
import { apiGet } from '../lib/api'

const report = await apiGet('/compliance/decision/report-123')
```

### POST Request
```typescript
import { apiPost } from '../lib/api'

const result = await apiPost('/compliance/decision', {
  document_id: 'doc-123'
})
```

### File Upload
```typescript
import { uploadFile } from '../lib/api'

const result = await uploadFile('/documents/upload', file)
```

### Error Handling
```typescript
import { ApiError } from '../lib/api'

try {
  const data = await apiGet('/some/endpoint')
} catch (err) {
  if (err instanceof ApiError) {
    console.error(`Error ${err.status}: ${err.detail}`)
  }
}
```

## Key Features Implemented

✅ Professional government-service UI
✅ Responsive layout (works on laptop/desktop)
✅ Semantic HTML with accessibility focus
✅ Keyboard navigation and visible focus states
✅ No official government branding (PolicyGuard AI only)
✅ Clear compliance disclaimer in footer
✅ Type-safe API integration
✅ Proper error states and loading indicators
✅ Modular component architecture
✅ Reusable UI component library
✅ No frontend decision logic (displays backend decisions only)
✅ Evidence traceability display
✅ Officer review controls
✅ Status/risk color coding with text labels

## Integration Points with Backend

1. **Document Upload**: `POST /documents/upload`
2. **Compliance Decision**: `POST /compliance/decision`
3. **Requirement Explanation**: `GET /compliance/requirements/{id}/explanation`
4. **Document Metadata**: `GET /documents/{id}`
5. **Analysis Details**: `GET /compliance/analyses/{id}`

All backends implemented in Phase 5-8; frontend reuses existing endpoints without modification.

## Development Workflow

1. **Add New Page**: Create `.tsx` file in `pages/`
2. **Add UI Component**: Add to `components/UI.tsx` or create new component file
3. **Add Type**: Define in `lib/types.ts`
4. **Call API**: Use `apiGet`, `apiPost`, or `uploadFile` from `lib/api.ts`
5. **Apply Styling**: Use `COLORS` from `lib/utils.ts` for consistency

## Deployment

### Docker (Production)
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY frontend .
RUN npm install
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Environment Variables
Create `.env.local`:
```
NEXT_PUBLIC_API_URL=http://your-backend-url/api/v1
```

## Testing

Integration tests provided in `__tests__/api.integration.test.ts`

Run tests:
```bash
npm run test
```

Tests validate:
- API client construction
- Type safety
- Error handling
- File upload validation
- JSON serialization

## Accessibility

- Semantic HTML (`<main>`, `<nav>`, `<header>`, `<footer>`, etc.)
- Proper heading hierarchy
- ARIA labels on buttons
- Keyboard navigation support
- Visible focus states (2px outline on buttons/inputs)
- Sufficient color contrast
- Text alternatives for icons
- Form labels and error messages

## Performance Considerations

- Lazy loading of components via Next.js dynamic imports (can be added)
- Efficient state management (minimal re-renders)
- No external CDN dependencies
- Inline CSS-in-JS for small component styles
- Tailwind CSS for utility classes

## Demo Experience (SIH Judges)

Optimal flow:
1. Dashboard loads with empty state
2. Click "Upload Document" → Go to Documents page
3. Drag/select PDF file → Upload
4. Once uploaded, click "Review" → Compliance Review page
5. See requirements list on left, click each to view explanation
6. See officer decision controls on right
7. Click accept/flag/reject to simulate decision
8. View Reports page for final report

## Known Limitations & Future Work

- Officer decision recording is UI-ready but backend integration pending
- Report export (PDF/print) is UI-ready but functionality pending
- Dashboard stats require aggregation API endpoint (can be added)
- Real-time upload progress requires WebSocket support (can be added)
- Advanced filtering/search on requirements list (can be added)
- Batch operations on requirements (can be added)

## Production Checklist

- [ ] Backend API URL configured in environment
- [ ] HTTPS enabled
- [ ] CORS headers configured on backend
- [ ] API rate limiting configured
- [ ] User authentication/authorization (if required)
- [ ] Audit logging for officer decisions
- [ ] PDF export functionality
- [ ] User preference storage (localStorage)
- [ ] Multi-user support / session management
- [ ] Backup/archive strategy for reports

## Support

For issues or questions:
1. Check `lib/types.ts` for available data types
2. Check `lib/api.ts` for API client examples
3. Review existing components in `components/`
4. Check pages for integration patterns

---

**Phase 9 Implementation**: Professional procurement compliance officer frontend for PolicyGuard AI. AI analysis is advisory; final decision remains with authorized officer.

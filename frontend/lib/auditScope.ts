/**
 * Audit-trail scoping for the compliance review page.
 *
 * Officer decisions are recorded in the audit chain with entity_id = report_id.
 * This pure helper keeps the displayed audit trail scoped to the currently
 * viewed report so events from other reports never leak in.
 */

export interface AuditEventLike {
  event_id: string
  actor: string
  action: string
  entity_id: string
  reason?: string | null
  comment?: string | null
  timestamp: string
}

/**
 * Return only the audit events that belong to the given report.
 *
 * Events are scoped by entity_id (the report the decision was recorded for).
 * If the backend query already filtered server-side, this double-checks the
 * scope so unrelated events can never render for the wrong report.
 */
export function scopeAuditEventsToReport(
  events: AuditEventLike[],
  reportId: string,
  limit = 10,
): AuditEventLike[] {
  if (!reportId) return []
  return events.filter((e) => e && e.entity_id === reportId).slice(0, limit)
}

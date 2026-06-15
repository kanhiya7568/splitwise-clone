import React, { useState, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Upload, FileText, AlertTriangle, CheckCircle2, XCircle, Info, ChevronDown, ChevronUp } from 'lucide-react'
import { toast } from 'sonner'
import api from '../lib/axios'
import { useGroups } from '../hooks'
import { Card, Button, Select, Badge, Skeleton, StatCard } from '../components/ui'
import { formatDate } from '../lib/utils'
import { cn } from '../lib/utils'
import type { PaginatedResponse } from '../types'

// ── Types ──────────────────────────────────────────────────────────────────────

interface ImportIssue {
  id: number
  csv_row_number: number
  anomaly_type: string
  anomaly_type_display: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  original_data: Record<string, string>
  action_taken: string
  action_taken_display: string
  resolution_notes: string
  created_at: string
}

interface ImportSession {
  id: number
  uploaded_file_name: string
  status: string
  status_display: string
  uploaded_by_name: string
  target_group: number | null
  total_rows: number
  valid_rows: number
  imported_rows: number
  skipped_rows: number
  anomaly_count: number
  usd_to_inr_rate: string
  started_at: string
  completed_at: string | null
  issues: ImportIssue[]
}

// ── Severity styling ───────────────────────────────────────────────────────────

const severityConfig = {
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20', badge: 'default' as const },
  warning: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20', badge: 'warning' as const },
  error: { icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/20', badge: 'error' as const },
  critical: { icon: XCircle, color: 'text-rose-600', bg: 'bg-rose-600/10 border-rose-600/20', badge: 'error' as const },
}

// ── Issue Row ─────────────────────────────────────────────────────────────────

function IssueRow({ issue }: { issue: ImportIssue }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = severityConfig[issue.severity] ?? severityConfig.info
  const Icon = cfg.icon

  return (
    <div className={cn('border rounded-xl overflow-hidden', cfg.bg)}>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-3 p-3 text-left hover:bg-white/5 transition-colors"
      >
        <Icon className={cn('size-4 shrink-0', cfg.color)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-white">Row {issue.csv_row_number}</span>
            <Badge variant={cfg.badge} className="text-[10px]">{issue.anomaly_type_display}</Badge>
            <Badge variant="default" className="text-[10px] opacity-60">{issue.action_taken_display}</Badge>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 truncate">{issue.resolution_notes}</p>
        </div>
        {expanded ? <ChevronUp className="size-4 text-zinc-500 shrink-0" /> : <ChevronDown className="size-4 text-zinc-500 shrink-0" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          <p className="text-sm text-zinc-300">{issue.resolution_notes}</p>
          <div className="bg-surface rounded-lg p-3">
            <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">Original CSV data</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(issue.original_data).filter(([, v]) => v).map(([k, v]) => (
                <div key={k} className="flex gap-2 text-xs">
                  <span className="text-zinc-500 shrink-0">{k}:</span>
                  <span className="text-zinc-300 truncate">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Session Detail Card ───────────────────────────────────────────────────────

function SessionDetail({ session }: { session: ImportSession }) {
  const [filterSeverity, setFilterSeverity] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')

  const anomalyTypes = [...new Set(session.issues.map(i => i.anomaly_type))]

  const filtered = session.issues.filter(i => {
    if (filterSeverity !== 'all' && i.severity !== filterSeverity) return false
    if (filterType !== 'all' && i.anomaly_type !== filterType) return false
    return true
  })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Total Rows" value={String(session.total_rows)} />
        <StatCard label="Imported" value={String(session.imported_rows)} color="green" />
        <StatCard label="Skipped" value={String(session.skipped_rows)} color={session.skipped_rows > 0 ? 'red' : 'default'} />
        <StatCard label="Anomalies" value={String(session.anomaly_count)} color={session.anomaly_count > 0 ? 'red' : 'default'} />
      </div>

      {/* Metadata */}
      <Card className="p-4 text-sm text-zinc-400 flex flex-wrap gap-x-6 gap-y-1">
        <span>File: <span className="text-white">{session.uploaded_file_name}</span></span>
        <span>USD→INR: <span className="text-white">{session.usd_to_inr_rate}</span></span>
        <span>Started: <span className="text-white">{formatDate(session.started_at)}</span></span>
        {session.completed_at && <span>Completed: <span className="text-white">{formatDate(session.completed_at)}</span></span>}
      </Card>

      {/* Anomaly breakdown chart */}
      {session.anomaly_count > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-white mb-3">Anomaly Breakdown</h3>
          <div className="space-y-2">
            {anomalyTypes.map(type => {
              const count = session.issues.filter(i => i.anomaly_type === type).length
              const pct = Math.round((count / session.anomaly_count) * 100)
              const label = session.issues.find(i => i.anomaly_type === type)?.anomaly_type_display ?? type
              return (
                <div key={type} className="flex items-center gap-3">
                  <p className="text-xs text-zinc-400 w-44 shrink-0 truncate">{label}</p>
                  <div className="flex-1 bg-white/5 rounded-full h-1.5">
                    <div className="bg-indigo-500 h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-zinc-400 w-6 text-right">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Issue list */}
      {session.issues.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h3 className="text-sm font-semibold text-white">{session.issues.length} Issues Detected</h3>
            <div className="flex gap-2">
              <select
                value={filterSeverity}
                onChange={e => setFilterSeverity(e.target.value)}
                className="bg-surface-2 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none"
              >
                <option value="all">All severities</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
              </select>
              <select
                value={filterType}
                onChange={e => setFilterType(e.target.value)}
                className="bg-surface-2 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none"
              >
                <option value="all">All types</option>
                {anomalyTypes.map(t => {
                  const label = session.issues.find(i => i.anomaly_type === t)?.anomaly_type_display ?? t
                  return <option key={t} value={t}>{label}</option>
                })}
              </select>
            </div>
          </div>
          <div className="space-y-2">
            {filtered.map(issue => <IssueRow key={issue.id} issue={issue} />)}
            {filtered.length === 0 && (
              <p className="text-sm text-zinc-500 text-center py-8">No issues match the current filter</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Session List Item ─────────────────────────────────────────────────────────

interface SessionListItem {
  id: number
  uploaded_file_name: string
  status: string
  status_display: string
  total_rows: number
  imported_rows: number
  skipped_rows: number
  anomaly_count: number
  started_at: string
  completed_at: string | null
}

function SessionListCard({ s, onSelect, selected }: { s: SessionListItem; onSelect: () => void; selected: boolean }) {
  return (
    <Card
      className={cn('p-4 cursor-pointer hover:border-white/15 transition-all', selected && 'border-indigo-500/40 bg-indigo-500/5')}
      onClick={onSelect}
    >
      <div className="flex items-center gap-3">
        <FileText className="size-5 text-indigo-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">{s.uploaded_file_name}</p>
          <p className="text-xs text-zinc-500">{formatDate(s.started_at)} · {s.total_rows} rows</p>
        </div>
        <div className="text-right shrink-0">
          <div className={cn('flex items-center gap-1 text-xs font-medium',
            s.status === 'completed' ? 'text-emerald-400' : s.status === 'failed' ? 'text-rose-400' : 'text-amber-400')}>
            {s.status === 'completed' ? <CheckCircle2 className="size-3" /> : <AlertTriangle className="size-3" />}
            {s.status_display}
          </div>
          {s.anomaly_count > 0 && (
            <p className="text-xs text-amber-400 mt-0.5">{s.anomaly_count} anomalies</p>
          )}
        </div>
      </div>
    </Card>
  )
}

// ── Main Import Page ──────────────────────────────────────────────────────────

export function ImportPage() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<string>('')
  const [activeSession, setActiveSession] = useState<ImportSession | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const { data: groupsData } = useGroups()
  const groups = groupsData?.results ?? []

  const sessionsQuery = useQuery({
    queryKey: ['import-sessions'],
    queryFn: () => api.get<PaginatedResponse<SessionListItem>>('/api/imports/').then(r => r.data),
  })
  const sessions = sessionsQuery.data?.results ?? []

  const sessionDetailQuery = useQuery({
    queryKey: ['import-session', activeSession?.id],
    queryFn: () => api.get<ImportSession>(`/api/imports/${activeSession!.id}/`).then(r => r.data),
    enabled: !!activeSession?.id,
  })

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile || !selectedGroupId) throw new Error('File and group required')
      const form = new FormData()
      form.append('file', selectedFile)
      form.append('group_id', selectedGroupId)
      return api.post<ImportSession>('/api/imports/upload/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }).then(r => r.data)
    },
    onSuccess: (session) => {
      toast.success(`Import complete! ${session.imported_rows} rows imported, ${session.anomaly_count} anomalies detected.`)
      setActiveSession(session)
      setSelectedFile(null)
      sessionsQuery.refetch()
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error
      toast.error(msg ?? 'Import failed')
    },
  })

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file?.name.endsWith('.csv')) setSelectedFile(file)
    else toast.error('Only .csv files are accepted')
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setSelectedFile(file)
  }

  const loadSessionDetail = (session: SessionListItem) => {
    setActiveSession(session as ImportSession)
  }

  const detailData = sessionDetailQuery.data ?? activeSession

  return (
    <div className="p-6 max-w-5xl mx-auto animate-fade-in space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">CSV Import</h1>
        <p className="text-zinc-400 text-sm mt-1">
          Import expenses from a CSV file. All anomalies are detected, documented, and reported.
        </p>
      </div>

      {/* Upload area */}
      <Card className="p-6">
        <h2 className="text-base font-semibold text-white mb-4">Upload expenses_export.csv</h2>
        <div className="space-y-4">
          {/* Group selector */}
          <Select
            label="Target group"
            value={selectedGroupId}
            onChange={e => setSelectedGroupId(e.target.value)}
          >
            <option value="">Select a group</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </Select>

          {/* Drop zone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            className={cn(
              'border-2 border-dashed rounded-xl p-8 flex flex-col items-center gap-3 cursor-pointer transition-all',
              isDragging ? 'border-indigo-500 bg-indigo-500/10' : 'border-white/10 hover:border-white/20 hover:bg-white/3'
            )}
          >
            <div className={cn('size-12 rounded-2xl flex items-center justify-center transition-all',
              isDragging ? 'bg-indigo-500/20' : 'bg-white/5')}>
              <Upload className={cn('size-6', isDragging ? 'text-indigo-400' : 'text-zinc-400')} />
            </div>
            {selectedFile ? (
              <div className="text-center">
                <p className="text-white font-medium">{selectedFile.name}</p>
                <p className="text-xs text-zinc-400">{(selectedFile.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-white">Drop your CSV here, or click to browse</p>
                <p className="text-xs text-zinc-500 mt-1">Only .csv files · UTF-8 encoded</p>
              </div>
            )}
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
          </div>

          {/* Import button */}
          <Button
            className="w-full"
            disabled={!selectedFile || !selectedGroupId}
            loading={uploadMutation.isPending}
            onClick={() => uploadMutation.mutate()}
          >
            <Upload className="size-4" />
            {uploadMutation.isPending ? 'Processing…' : 'Import CSV'}
          </Button>
        </div>
      </Card>

      {/* Results panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Session history */}
        <div>
          <h2 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider">Import History</h2>
          {sessionsQuery.isLoading ? (
            <div className="space-y-2">{[1, 2].map(i => <Skeleton key={i} className="h-16" />)}</div>
          ) : sessions.length === 0 ? (
            <Card className="p-6 text-center">
              <p className="text-zinc-500 text-sm">No imports yet</p>
            </Card>
          ) : (
            <div className="space-y-2">
              {sessions.map(s => (
                <SessionListCard
                  key={s.id}
                  s={s}
                  selected={activeSession?.id === s.id}
                  onSelect={() => loadSessionDetail(s)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Session detail */}
        <div className="lg:col-span-2">
          {sessionDetailQuery.isLoading ? (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-3">{[1,2,3,4].map(i => <Skeleton key={i} className="h-20" />)}</div>
              <Skeleton className="h-48" />
            </div>
          ) : detailData ? (
            <SessionDetail session={detailData as ImportSession} />
          ) : (
            <Card className="p-12 flex flex-col items-center gap-4 text-center">
              <div className="size-14 bg-white/5 rounded-2xl flex items-center justify-center">
                <FileText className="size-6 text-zinc-400" />
              </div>
              <div>
                <p className="text-white font-medium">Select an import to view details</p>
                <p className="text-zinc-500 text-sm mt-1">Or upload a new CSV above</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

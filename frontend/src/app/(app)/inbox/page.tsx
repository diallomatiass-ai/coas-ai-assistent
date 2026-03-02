'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import { useWebSocket } from '@/hooks/useWebSocket'
import InboxList from '@/components/InboxList'
import EmailDetail from '@/components/EmailDetail'
import AiSuggestionCard from '@/components/AiSuggestionCard'
import ConversationPanel from '@/components/ConversationPanel'
import ComposeEmail from '@/components/ComposeEmail'
import { useTranslation } from '@/lib/i18n'
import { Sparkles, Loader2, X, AlertTriangle, Search, PenSquare, Bell, Send } from 'lucide-react'

const categories = ['inquiry', 'complaint', 'order', 'support', 'spam', 'other']
const urgencies = ['high', 'medium', 'low']

export default function InboxPage() {
  const { t } = useTranslation()
  const [emails, setEmails] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [activeUrgency, setActiveUrgency] = useState<string | null>(null)

  // Search
  const [searchQuery, setSearchQuery] = useState('')
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // View: inbox | sent
  const [view, setView] = useState<'inbox' | 'sent'>('inbox')
  const [sentEmails, setSentEmails] = useState<any[]>([])
  const [sentLoading, setSentLoading] = useState(false)

  // Detail panel
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedEmail, setSelectedEmail] = useState<any>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [generating, setGenerating] = useState(false)

  // Compose
  const [composeOpen, setComposeOpen] = useState(false)

  // Reminders
  const [reminders, setReminders] = useState<any[]>([])
  const [remindersOpen, setRemindersOpen] = useState(true)

  const categoryLabels: Record<string, string> = {
    inquiry: t('inquiry'), complaint: t('complaint'), order: t('order'),
    support: t('support'), spam: t('spam'), other: t('other'),
  }
  const urgencyLabels: Record<string, string> = { high: t('high'), medium: t('medium'), low: t('low') }

  // Debounce search
  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => {
      setDebouncedSearch(searchQuery)
    }, 300)
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current) }
  }, [searchQuery])

  const fetchEmails = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (activeCategory) params.category = activeCategory
      if (activeUrgency) params.urgency = activeUrgency
      if (debouncedSearch) params.search = debouncedSearch
      const data = await api.listEmails(params)
      setEmails(data)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const fetchSentEmails = async () => {
    setSentLoading(true)
    try {
      const data = await api.listSentEmails()
      setSentEmails(data || [])
    } catch (err) { console.error(err) }
    finally { setSentLoading(false) }
  }

  const fetchReminders = async () => {
    try {
      const data = await api.listReminders()
      setReminders(data || [])
    } catch { /* ignore */ }
  }

  useEffect(() => {
    if (view === 'inbox') fetchEmails()
    else fetchSentEmails()
  }, [activeCategory, activeUrgency, debouncedSearch, view])

  useEffect(() => { fetchReminders() }, [])

  // WebSocket: auto-refresh indbakken når ny email modtages
  useWebSocket((event) => {
    if (event.type === 'new_email' && view === 'inbox') {
      fetchEmails()
    }
  })

  const fetchDetail = useCallback(async (id: string) => {
    setDetailLoading(true)
    try {
      const data = await api.getEmail(id)
      setSelectedEmail(data)
    } catch (err) {
      console.error('Failed to load email:', err)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const handleSelect = (id: string) => {
    setSelectedId(id)
    setSelectedEmail(null)
    fetchDetail(id)
  }

  const handleClose = () => {
    setSelectedId(null)
    setSelectedEmail(null)
  }

  const handleAction = async (suggestionId: string, action: string, editedText?: string) => {
    await api.actionSuggestion(suggestionId, action, editedText)
    if (selectedId) await fetchDetail(selectedId)
  }

  const handleSend = async (suggestionId: string) => {
    await api.sendSuggestion(suggestionId)
    if (selectedId) await fetchDetail(selectedId)
    await fetchEmails()
  }

  const handleGenerate = async () => {
    if (!selectedId) return
    setGenerating(true)
    try {
      await api.generateSuggestion(selectedId)
      await fetchDetail(selectedId)
    } catch (err: any) {
      alert(err.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleDismissReminder = async (id: string) => {
    try {
      await api.dismissReminder(id)
      setReminders(prev => prev.filter(r => r.id !== id))
    } catch { /* ignore */ }
  }

  const pillClass = (active: boolean) =>
    `px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
      active
        ? 'bg-[#162249] dark:bg-[#42D1B9]/20 text-white dark:text-[#42D1B9] border-[#162249] dark:border-[#42D1B9]/40'
        : 'bg-[var(--surface)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--text-muted)] hover:text-[var(--text-primary)]'
    }`

  const hasSuggestions = selectedEmail?.suggestions?.length > 0

  // Split emails: urgent vs rest (only when no urgency filter is active)
  const urgentEmails = !activeUrgency ? emails.filter(e => e.urgency === 'high' && !e.is_read) : []
  const restEmails = !activeUrgency ? emails.filter(e => !(e.urgency === 'high' && !e.is_read)) : emails
  const unreadCount = emails.filter(e => !e.is_read).length

  return (
    <div className="h-full flex flex-col">
      {/* Filter bar */}
      <div className="p-3 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0 space-y-2">
        {/* Row 1: Search + title + compose */}
        <div className="flex items-center gap-2">
          <h1 className="text-base font-bold text-[var(--text-primary)] mr-1">{t('inbox')}</h1>
          {unreadCount > 0 && view === 'inbox' && (
            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-[#162249] dark:bg-[#42D1B9] text-white dark:text-[#0D1B3E] mr-1">
              {unreadCount}
            </span>
          )}
          <div className="flex-1 relative max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('searchPlaceholder')}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] focus:border-transparent placeholder:text-[var(--text-muted)]"
            />
          </div>
          <button
            onClick={() => setComposeOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-[#162249] hover:bg-[#1e2d6b] text-white transition-colors ml-auto"
          >
            <PenSquare className="w-3.5 h-3.5" />
            {t('newEmail')}
          </button>
        </div>

        {/* Row 2: Tabs */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => { setView('inbox'); setSelectedId(null); setSelectedEmail(null) }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              view === 'inbox'
                ? 'bg-[#162249] dark:bg-[#42D1B9]/20 text-white dark:text-[#42D1B9]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            {t('inbox')}
          </button>
          <button
            onClick={() => { setView('sent'); setSelectedId(null); setSelectedEmail(null) }}
            className={`inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              view === 'sent'
                ? 'bg-[#162249] dark:bg-[#42D1B9]/20 text-white dark:text-[#42D1B9]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            <Send className="w-3 h-3" />
            {t('sentEmails')}
          </button>
        </div>

        {/* Row 3: Category + urgency filters (only in inbox view) */}
        {view === 'inbox' && (
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => { setActiveCategory(null); setActiveUrgency(null) }} className={pillClass(!activeCategory && !activeUrgency)}>{t('all')}</button>
            {categories.map((cat) => (
              <button key={cat} onClick={() => setActiveCategory(activeCategory === cat ? null : cat)} className={pillClass(activeCategory === cat)}>
                {categoryLabels[cat] || cat}
              </button>
            ))}
            <div className="w-px bg-[var(--border)] mx-1 self-stretch" />
            {urgencies.map((urg) => (
              <button key={urg} onClick={() => setActiveUrgency(activeUrgency === urg ? null : urg)} className={pillClass(activeUrgency === urg)}>
                {urgencyLabels[urg]}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Reminders banner */}
      {view === 'inbox' && reminders.length > 0 && (
        <div className="border-b border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 flex-shrink-0">
          <button
            onClick={() => setRemindersOpen(!remindersOpen)}
            className="w-full flex items-center gap-2 px-4 py-2"
          >
            <Bell className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            <span className="text-xs font-bold text-amber-700 dark:text-amber-400 uppercase tracking-wider">
              {t('reminders')}
            </span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-600 text-white">
              {reminders.length}
            </span>
          </button>
          {remindersOpen && (
            <div className="px-4 pb-3 space-y-1.5">
              {reminders.map((r: any) => (
                <div
                  key={r.id}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/60 dark:bg-white/5 text-sm"
                >
                  <button
                    onClick={() => { handleSelect(r.email_id); }}
                    className="flex-1 text-left text-[var(--text-primary)] hover:underline truncate"
                  >
                    {r.message}
                  </button>
                  <button
                    onClick={() => handleDismissReminder(r.id)}
                    className="flex-shrink-0 px-2 py-1 text-[10px] font-medium rounded bg-amber-200/50 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-500/30 transition-colors"
                  >
                    {t('dismiss')}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Split view */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Email list */}
        <div className={`${selectedId ? 'w-2/5 border-r border-[var(--border)]' : 'w-full'} flex flex-col min-h-0 transition-all`}>
          {view === 'inbox' ? (
            loading ? (
              <div className="p-8 text-center text-[var(--text-muted)]">{t('loading')}</div>
            ) : (
              <div className="flex-1 overflow-y-auto">
                {/* Urgent section */}
                {urgentEmails.length > 0 && (
                  <div className="flex-shrink-0">
                    <div className="px-4 py-2 bg-red-50 dark:bg-red-500/10 border-b border-red-200 dark:border-red-500/20 flex items-center gap-1.5 sticky top-0 z-10">
                      <AlertTriangle className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
                      <span className="text-xs font-bold text-red-700 dark:text-red-400 uppercase tracking-wider">
                        Haster
                      </span>
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-600 text-white ml-1">
                        {urgentEmails.length}
                      </span>
                    </div>
                    <InboxList emails={urgentEmails} onSelect={handleSelect} selectedId={selectedId || undefined} />
                  </div>
                )}

                {/* Rest of emails */}
                {urgentEmails.length > 0 && restEmails.length > 0 && (
                  <div className="px-4 py-2 bg-[var(--surface)] border-b border-[var(--border)] border-t border-t-[var(--border)] sticky top-0 z-10">
                    <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
                      {t('all')}
                    </span>
                  </div>
                )}
                <InboxList emails={restEmails} onSelect={handleSelect} selectedId={selectedId || undefined} />
              </div>
            )
          ) : (
            /* Sent emails view */
            sentLoading ? (
              <div className="p-8 text-center text-[var(--text-muted)]">{t('loading')}</div>
            ) : sentEmails.length === 0 ? (
              <div className="p-8 text-center text-[var(--text-muted)]">{t('noSentEmails')}</div>
            ) : (
              <div className="flex-1 overflow-y-auto divide-y divide-[var(--border)]">
                {sentEmails.map((item: any) => (
                  <button
                    key={item.id}
                    onClick={() => item.original_email_id ? handleSelect(item.original_email_id) : null}
                    className={`w-full text-left px-4 py-3 hover:bg-[var(--surface-hover)] transition-colors ${
                      selectedId && selectedId === item.original_email_id ? 'bg-[#42D1B9]/10' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-[var(--text-primary)] truncate">
                        {t('sentTo')}: {item.to_address}
                      </span>
                      <span className="text-[10px] text-[var(--text-muted)] ml-2 flex-shrink-0">
                        {item.sent_at ? new Date(item.sent_at).toLocaleDateString('da-DK', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] truncate mt-0.5">{item.subject || '(intet emne)'}</p>
                    {item.body_preview && (
                      <p className="text-xs text-[var(--text-muted)] truncate mt-0.5">{item.body_preview}</p>
                    )}
                    <span className={`inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded ${
                      item.type === 'compose'
                        ? 'bg-[#42D1B9]/15 text-[#162249] dark:bg-[#42D1B9]/20 dark:text-[#42D1B9]'
                        : 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300'
                    }`}>
                      {item.type === 'compose' ? t('newEmail') : 'AI-svar'}
                    </span>
                  </button>
                ))}
              </div>
            )
          )}
        </div>

        {/* Right: Email detail + AI */}
        {selectedId && (
          <div className="w-3/5 flex flex-col min-h-0">
            {/* Detail header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0">
              <div className="flex items-center gap-2">
                {!hasSuggestions && selectedEmail && (
                  <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg disabled:opacity-50"
                  >
                    {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    {generating ? 'Genererer...' : 'Generer AI-forslag'}
                  </button>
                )}
              </div>
              <button onClick={handleClose} className="p-1.5 rounded-lg hover:bg-[var(--surface-hover)] transition-colors">
                <X className="w-4 h-4 text-[var(--text-muted)]" />
              </button>
            </div>

            {/* Detail content */}
            <div className="flex-1 overflow-y-auto p-5">
              {detailLoading ? (
                <div className="text-center text-[var(--text-muted)] py-12">{t('loading')}</div>
              ) : selectedEmail ? (
                <div className="space-y-5 max-w-3xl">
                  {/* Email body */}
                  <div className="card p-5">
                    <EmailDetail email={selectedEmail} />
                  </div>

                  {/* AI suggestions */}
                  <div>
                    <h3 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider mb-3">{t('aiSuggestions')}</h3>
                    {hasSuggestions ? (
                      <div className="space-y-3">
                        {selectedEmail.suggestions.map((s: any) => (
                          <AiSuggestionCard key={s.id} suggestion={s} onAction={handleAction} onSend={handleSend} />
                        ))}
                      </div>
                    ) : (
                      <div className="card p-4 text-sm text-[var(--text-muted)]">
                        <p className="mb-3">{selectedEmail.processed ? t('noSuggestions') : t('awaitingAi')}</p>
                        <button
                          onClick={handleGenerate}
                          disabled={generating}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-[#42D1B9]/15 dark:bg-[#42D1B9]/20 hover:bg-[#42D1B9]/25 text-[#162249] dark:text-[#42D1B9] disabled:opacity-50 transition-colors"
                        >
                          {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                          {generating ? 'Genererer...' : 'Generer AI-forslag nu'}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Classification */}
                  {selectedEmail.category && (
                    <div className="card p-4">
                      <h4 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">{t('classification')}</h4>
                      <div className="space-y-1.5 text-sm">
                        <div className="flex justify-between">
                          <span className="text-[var(--text-muted)]">{t('category')}</span>
                          <span className="font-medium text-[var(--text-primary)] capitalize">{selectedEmail.category}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[var(--text-muted)]">{t('priority')}</span>
                          <span className="font-medium text-[var(--text-primary)] capitalize">{selectedEmail.urgency}</span>
                        </div>
                        {selectedEmail.topic && (
                          <div className="flex justify-between">
                            <span className="text-[var(--text-muted)]">{t('topic')}</span>
                            <span className="font-medium text-[var(--text-primary)]">{selectedEmail.topic}</span>
                          </div>
                        )}
                        {selectedEmail.confidence != null && (
                          <div className="flex justify-between">
                            <span className="text-[var(--text-muted)]">{t('confidence')}</span>
                            <span className="font-medium text-[#42D1B9]">{Math.round(selectedEmail.confidence * 100)}%</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Conversation panel (thread + customer history) */}
                  <ConversationPanel emailId={selectedId} onSelect={handleSelect} />
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>

      {/* Compose modal */}
      {composeOpen && (
        <ComposeEmail
          onClose={() => setComposeOpen(false)}
          onSent={() => { fetchEmails(); fetchSentEmails() }}
        />
      )}
    </div>
  )
}

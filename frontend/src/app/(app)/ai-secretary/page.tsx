'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { useTranslation } from '@/lib/i18n'
import { Phone, PhoneIncoming, CheckCircle2, Settings2, Calendar, Clock, Plus, X, Eye } from 'lucide-react'
import SetupWizard from '@/components/secretary/SetupWizard'
import ScriptEditor from '@/components/secretary/ScriptEditor'
import CallLog from '@/components/secretary/CallLog'

interface Secretary {
  id: string
  business_name: string
  industry: string
  phone_number: string | null
  greeting_text: string
  system_prompt: string
  required_fields: string[]
  knowledge_items: Record<string, string>
  is_active: boolean
  confirmation_enabled: boolean
  confirmation_template: string | null
  response_deadline_hours: number
}

interface BookingRules {
  enabled: boolean
  work_days: number[]
  work_hours: { start: string; end: string }
  slot_duration_minutes: number
  buffer_minutes: number
  max_bookings_per_day: number
  advance_booking_days: number
  min_notice_hours: number
  blocked_dates: string[]
  custom_slots: Record<string, unknown>
}

interface TimeSlot {
  date: string
  start_time: string
  end_time: string
}

const DEFAULT_BOOKING_RULES: BookingRules = {
  enabled: false,
  work_days: [0, 1, 2, 3, 4],
  work_hours: { start: '07:00', end: '16:00' },
  slot_duration_minutes: 60,
  buffer_minutes: 30,
  max_bookings_per_day: 5,
  advance_booking_days: 14,
  min_notice_hours: 2,
  blocked_dates: [],
  custom_slots: {},
}

interface Call {
  id: string
  caller_name: string | null
  caller_phone: string | null
  caller_address: string | null
  summary: string
  transcript: string | null
  urgency: string
  status: string
  notes: string | null
  called_at: string
  customer_id?: string | null
  confirmation_sent_at?: string | null
}

export default function AiSecretaryPage() {
  const { t } = useTranslation()
  const router = useRouter()
  const [secretary, setSecretary] = useState<Secretary | null>(null)
  const [calls, setCalls] = useState<Call[]>([])
  const [loading, setLoading] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [saving, setSaving] = useState(false)
  const [bookingRules, setBookingRules] = useState<BookingRules>(DEFAULT_BOOKING_RULES)
  const [savingBooking, setSavingBooking] = useState(false)
  const [newBlockedDate, setNewBlockedDate] = useState('')
  const [previewSlots, setPreviewSlots] = useState<TimeSlot[] | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [hasCalendar, setHasCalendar] = useState(false)

  const fetchData = async () => {
    try {
      const sec = await api.getSecretary()
      setSecretary(sec)
      if (sec) {
        const callData = await api.getCalls()
        setCalls(callData)
      }
    } catch (err) {
      console.error('Failed to load secretary:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchBookingRules = async () => {
    try {
      const data = await api.getBookingRules()
      if (data) setBookingRules({ ...DEFAULT_BOOKING_RULES, ...data })
    } catch (err) {
      console.error('Failed to load booking rules:', err)
    }
  }

  useEffect(() => {
    fetchData()
    fetchBookingRules()
    api.listCalendarAccounts().then(accs => setHasCalendar(Array.isArray(accs) && accs.length > 0)).catch(() => {})
  }, [])

  const handleSetupComplete = () => {
    fetchData()
  }

  const handleUpdateSettings = async (updates: Partial<Secretary>) => {
    setSaving(true)
    try {
      const updated = await api.updateSecretary(updates)
      setSecretary(updated)
      setShowSettings(false)
    } catch (err) {
      console.error('Failed to update secretary:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveBookingRules = async () => {
    setSavingBooking(true)
    try {
      await api.updateBookingRules(bookingRules)
    } catch (err) {
      console.error('Failed to save booking rules:', err)
    } finally {
      setSavingBooking(false)
    }
  }

  const handleAddBlockedDate = async () => {
    if (!newBlockedDate) return
    try {
      await api.addBlockedDate(newBlockedDate)
      setBookingRules(prev => ({
        ...prev,
        blocked_dates: [...prev.blocked_dates, newBlockedDate].sort(),
      }))
      setNewBlockedDate('')
    } catch (err) {
      console.error('Failed to add blocked date:', err)
    }
  }

  const handleRemoveBlockedDate = async (date: string) => {
    try {
      await api.removeBlockedDate(date)
      setBookingRules(prev => ({
        ...prev,
        blocked_dates: prev.blocked_dates.filter(d => d !== date),
      }))
    } catch (err) {
      console.error('Failed to remove blocked date:', err)
    }
  }

  const handlePreviewAvailability = async () => {
    setLoadingPreview(true)
    try {
      const today = new Date()
      const from = today.toISOString().split('T')[0]
      const to = new Date(today.getTime() + 7 * 86400000).toISOString().split('T')[0]
      const data = await api.getBookingAvailability(from, to)
      setPreviewSlots(data?.slots || [])
    } catch (err) {
      console.error('Failed to preview availability:', err)
      setPreviewSlots([])
    } finally {
      setLoadingPreview(false)
    }
  }

  const toggleWorkDay = (day: number) => {
    setBookingRules(prev => ({
      ...prev,
      work_days: prev.work_days.includes(day)
        ? prev.work_days.filter(d => d !== day)
        : [...prev.work_days, day].sort(),
    }))
  }

  const DAY_NAMES = [
    t('monday'), t('tuesday'), t('wednesday'), t('thursday'),
    t('friday'), t('saturday'), t('sunday'),
  ]

  const handlePushOrdrestyring = useCallback(async (customerId: string) => {
    try {
      await api.pushToOrdrestyring(customerId)
      alert(t('ordrestyringSuccess'))
      fetchData()
    } catch (e: any) {
      alert(e.message || t('ordrestyringError'))
    }
  }, [t])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[var(--text-muted)]">{t('loading')}</div>
      </div>
    )
  }

  // Not configured — show setup wizard
  if (!secretary) {
    return (
      <div className="p-4 md:p-6 animate-fadeIn max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-xl md:text-2xl font-bold text-[var(--text-primary)]">
            {t('aiSecretary')}
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {t('setupWizardDesc')}
          </p>
        </div>
        <SetupWizard onComplete={handleSetupComplete} />
      </div>
    )
  }

  // Configured — show dashboard
  const newCallsList = calls.filter((c) => c.status === 'new').sort((a, b) => new Date(b.called_at).getTime() - new Date(a.called_at).getTime())
  const contactedCallsList = calls.filter((c) => c.status === 'contacted').sort((a, b) => new Date(b.called_at).getTime() - new Date(a.called_at).getTime())
  const resolvedCallsList = calls.filter((c) => c.status === 'resolved').sort((a, b) => new Date(b.called_at).getTime() - new Date(a.called_at).getTime())

  return (
    <div className="p-4 md:p-6 animate-fadeIn space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-[var(--text-primary)]">
            {t('secretaryDashboard')}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-sm text-[var(--text-muted)]">
              {secretary.business_name}
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-bold ${
              secretary.is_active
                ? 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400'
                : 'bg-[var(--surface-hover)] text-[var(--text-muted)]'
            }`}>
              {secretary.is_active ? t('active') : t('inactive')}
            </span>
          </div>
        </div>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-[var(--surface-hover)] text-[var(--text-secondary)] hover:bg-[var(--border)] transition-colors min-h-[44px]"
        >
          <Settings2 className="w-5 h-5" />
          {t('editSettings')}
        </button>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="card p-5 space-y-6">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">
            {t('editSettings')}
          </h2>
          <ScriptEditor
            greetingText={secretary.greeting_text}
            onGreetingChange={(v) => setSecretary({ ...secretary, greeting_text: v })}
            requiredFields={secretary.required_fields}
            onFieldsChange={(v) => setSecretary({ ...secretary, required_fields: v })}
            knowledgeItems={secretary.knowledge_items}
            onKnowledgeChange={(v) => setSecretary({ ...secretary, knowledge_items: v })}
            businessName={secretary.business_name}
          />

          {/* Bekræftelsesmail sektion */}
          <div className="pt-5 border-t border-[var(--border)]">
            <h3 className="text-base font-bold text-[var(--text-primary)] mb-4">
              {t('confirmationMail')}
            </h3>
            <div className="space-y-4">
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  onClick={() => setSecretary({ ...secretary, confirmation_enabled: !secretary.confirmation_enabled })}
                  className={`w-12 h-7 rounded-full transition-all flex items-center px-0.5 cursor-pointer ${
                    secretary.confirmation_enabled
                      ? 'bg-[#42D1B9] justify-end'
                      : 'bg-gray-300 dark:bg-zinc-600 justify-start'
                  }`}
                >
                  <div className="w-6 h-6 bg-white rounded-full shadow-sm" />
                </div>
                <span className="text-sm text-[var(--text-primary)]">
                  {t('confirmationEnabled')}
                </span>
              </label>

              {secretary.confirmation_enabled && (
                <>
                  <div>
                    <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-1 block">
                      {t('responseDeadlineHours')}
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={168}
                      value={secretary.response_deadline_hours}
                      onChange={(e) => setSecretary({ ...secretary, response_deadline_hours: parseInt(e.target.value) || 24 })}
                      className="w-24 px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-1 block">
                      {t('confirmationTemplate')}
                    </label>
                    <textarea
                      value={secretary.confirmation_template || 'Tak for din henvendelse til {business_name}.\n\nVi har modtaget din forespørgsel om: {summary}\n\nVi vender tilbage inden {response_deadline}.\n\nVenlig hilsen\n{business_name}'}
                      onChange={(e) => setSecretary({ ...secretary, confirmation_template: e.target.value })}
                      rows={6}
                      className="w-full px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] resize-none font-mono min-h-[44px]"
                    />
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Variabler: {'{business_name}'}, {'{summary}'}, {'{response_deadline}'}, {'{caller_name}'}
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* ── Booking-indstillinger ── */}
          <div className="pt-5 border-t border-[var(--border)]">
            <div className="flex items-center gap-2 mb-1">
              <Calendar className="w-5 h-5 text-[#42D1B9]" />
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                {t('bookingSettings')}
              </h3>
            </div>
            <p className="text-sm text-[var(--text-muted)] mb-4">{t('bookingSettingsDesc')}</p>

            {!hasCalendar && (
              <div className="p-3 mb-4 bg-amber-50 dark:bg-amber-500/10 rounded-lg border border-amber-200 dark:border-amber-500/20">
                <p className="text-sm text-amber-700 dark:text-amber-400">{t('calendarRequired')}</p>
              </div>
            )}

            <div className="space-y-5">
              {/* Aktivér booking */}
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  onClick={() => setBookingRules(prev => ({ ...prev, enabled: !prev.enabled }))}
                  className={`w-12 h-7 rounded-full transition-all flex items-center px-0.5 cursor-pointer ${
                    bookingRules.enabled
                      ? 'bg-[#42D1B9] justify-end'
                      : 'bg-gray-300 dark:bg-zinc-600 justify-start'
                  }`}
                >
                  <div className="w-6 h-6 bg-white rounded-full shadow-sm" />
                </div>
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)]">{t('bookingEnabled')}</span>
                  <p className="text-xs text-[var(--text-muted)]">{t('bookingEnabledDesc')}</p>
                </div>
              </label>

              {bookingRules.enabled && (
                <>
                  {/* Arbejdsdage */}
                  <div>
                    <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-2 block">{t('workDays')}</label>
                    <div className="flex flex-wrap gap-2">
                      {DAY_NAMES.map((name, i) => (
                        <button
                          key={i}
                          onClick={() => toggleWorkDay(i)}
                          className={`px-3 py-1.5 text-sm font-medium rounded-lg border transition-all ${
                            bookingRules.work_days.includes(i)
                              ? 'bg-[#42D1B9]/10 text-[#162249] dark:text-[#42D1B9] border-[#42D1B9]/30'
                              : 'text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700'
                          }`}
                        >
                          {name}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Arbejdstider */}
                  <div>
                    <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-2 block">{t('workHours')}</label>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-[var(--text-secondary)]">{t('workHoursStart')}</span>
                        <input
                          type="time"
                          value={bookingRules.work_hours.start}
                          onChange={e => setBookingRules(prev => ({ ...prev, work_hours: { ...prev.work_hours, start: e.target.value } }))}
                          className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                        />
                      </div>
                      <span className="text-[var(--text-muted)]">—</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-[var(--text-secondary)]">{t('workHoursEnd')}</span>
                        <input
                          type="time"
                          value={bookingRules.work_hours.end}
                          onChange={e => setBookingRules(prev => ({ ...prev, work_hours: { ...prev.work_hours, end: e.target.value } }))}
                          className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Numeriske indstillinger (2x2 grid) */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-1 block">{t('slotDuration')}</label>
                      <input
                        type="number"
                        min={15}
                        max={480}
                        step={15}
                        value={bookingRules.slot_duration_minutes}
                        onChange={e => setBookingRules(prev => ({ ...prev, slot_duration_minutes: parseInt(e.target.value) || 60 }))}
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-1 block">{t('bufferMinutes')}</label>
                      <input
                        type="number"
                        min={0}
                        max={120}
                        step={5}
                        value={bookingRules.buffer_minutes}
                        onChange={e => setBookingRules(prev => ({ ...prev, buffer_minutes: parseInt(e.target.value) || 0 }))}
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-1 block">{t('maxBookingsPerDay')}</label>
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={bookingRules.max_bookings_per_day}
                        onChange={e => setBookingRules(prev => ({ ...prev, max_bookings_per_day: parseInt(e.target.value) || 5 }))}
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-1 block">{t('advanceBookingDays')}</label>
                      <input
                        type="number"
                        min={1}
                        max={90}
                        value={bookingRules.advance_booking_days}
                        onChange={e => setBookingRules(prev => ({ ...prev, advance_booking_days: parseInt(e.target.value) || 14 }))}
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                      />
                    </div>
                  </div>

                  {/* Min notice */}
                  <div>
                    <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-1 block">{t('minNoticeHours')}</label>
                    <input
                      type="number"
                      min={0}
                      max={72}
                      value={bookingRules.min_notice_hours}
                      onChange={e => setBookingRules(prev => ({ ...prev, min_notice_hours: parseInt(e.target.value) || 0 }))}
                      className="w-24 px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                    />
                  </div>

                  {/* Blokerede datoer */}
                  <div>
                    <label className="text-xs font-bold text-[var(--text-muted)] uppercase mb-2 block">{t('blockedDates')}</label>
                    <p className="text-xs text-[var(--text-muted)] mb-2">{t('blockedDatesDesc')}</p>

                    {bookingRules.blocked_dates.length > 0 ? (
                      <div className="flex flex-wrap gap-2 mb-3">
                        {bookingRules.blocked_dates.map(date => (
                          <span key={date} className="inline-flex items-center gap-1 px-2.5 py-1 text-sm bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-500/20 rounded-lg">
                            {new Date(date + 'T00:00:00').toLocaleDateString('da-DK', { day: 'numeric', month: 'short', year: 'numeric' })}
                            <button onClick={() => handleRemoveBlockedDate(date)} className="p-0.5 hover:text-red-900 dark:hover:text-red-300">
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-[var(--text-muted)] mb-3">{t('noBlockedDates')}</p>
                    )}

                    <div className="flex items-center gap-2">
                      <input
                        type="date"
                        value={newBlockedDate}
                        onChange={e => setNewBlockedDate(e.target.value)}
                        min={new Date().toISOString().split('T')[0]}
                        className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-primary)] focus:ring-2 focus:ring-[#42D1B9] min-h-[44px]"
                      />
                      <button
                        onClick={handleAddBlockedDate}
                        disabled={!newBlockedDate}
                        className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-[var(--surface-hover)] text-[var(--text-secondary)] rounded-lg hover:bg-[var(--border)] disabled:opacity-50 transition-colors min-h-[44px]"
                      >
                        <Plus className="w-4 h-4" />
                        {t('addBlockedDate')}
                      </button>
                    </div>
                  </div>

                  {/* Preview ledige tider */}
                  <div>
                    <button
                      onClick={handlePreviewAvailability}
                      disabled={loadingPreview}
                      className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-[#42D1B9]/30 text-[#162249] dark:text-[#42D1B9] bg-[#42D1B9]/10 rounded-lg hover:bg-[#42D1B9]/20 disabled:opacity-50 transition-all"
                    >
                      <Eye className="w-4 h-4" />
                      {loadingPreview ? t('loading') : t('previewAvailability')}
                    </button>
                    <p className="text-xs text-[var(--text-muted)] mt-1">{t('previewAvailabilityDesc')}</p>

                    {previewSlots !== null && (
                      <div className="mt-3 p-4 bg-slate-50 dark:bg-zinc-900/50 rounded-lg border border-slate-200 dark:border-white/[0.04]">
                        {previewSlots.length === 0 ? (
                          <p className="text-sm text-[var(--text-muted)]">{t('noAvailableSlots')}</p>
                        ) : (
                          <div className="space-y-2">
                            {previewSlots.map((slot, i) => (
                              <div key={i} className="flex items-center gap-3 text-sm">
                                <span className="font-medium text-[var(--text-primary)] min-w-[100px]">
                                  {new Date(slot.date + 'T00:00:00').toLocaleDateString('da-DK', { weekday: 'short', day: 'numeric', month: 'short' })}
                                </span>
                                <div className="flex items-center gap-1 text-[var(--text-secondary)]">
                                  <Clock className="w-3.5 h-3.5 text-[#42D1B9]" />
                                  {slot.start_time} — {slot.end_time}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Gem booking-regler */}
                  <div className="flex justify-end">
                    <button
                      onClick={handleSaveBookingRules}
                      disabled={savingBooking}
                      className="px-4 py-2.5 text-sm font-medium bg-[#42D1B9] text-white rounded-lg hover:bg-[#38b8a2] disabled:opacity-50 transition-colors"
                    >
                      {savingBooking ? t('loading') : `${t('save')} ${t('bookingSettings').toLowerCase()}`}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              onClick={() => {
                setShowSettings(false)
                fetchData()
              }}
              className="px-5 py-2.5 rounded-lg text-sm font-medium bg-[var(--surface-hover)] text-[var(--text-secondary)] hover:bg-[var(--border)] transition-colors min-h-[44px]"
            >
              {t('cancel')}
            </button>
            <button
              onClick={() => handleUpdateSettings({
                greeting_text: secretary.greeting_text,
                required_fields: secretary.required_fields,
                knowledge_items: secretary.knowledge_items,
                confirmation_enabled: secretary.confirmation_enabled,
                confirmation_template: secretary.confirmation_template,
                response_deadline_hours: secretary.response_deadline_hours,
              } as any)}
              disabled={saving}
              className="btn-primary"
            >
              {saving ? t('loading') : t('save')}
            </button>
          </div>
        </div>
      )}

      {/* 3 Kanban-kolonner */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">

        {/* ── Kolonne 1: Nye opkald ── */}
        <section className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border)] bg-blue-50 dark:bg-blue-500/10">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-blue-700 dark:text-blue-400 flex items-center gap-1.5">
                <PhoneIncoming className="w-4 h-4" />
                Nye opkald
              </h2>
              <span className="text-2xl font-bold text-blue-700 dark:text-blue-400">{newCallsList.length}</span>
            </div>
          </div>
          {newCallsList.length > 0 ? (
            <CallLog calls={newCallsList} onCallUpdated={fetchData} onPushOrdrestyring={handlePushOrdrestyring} />
          ) : (
            <div className="py-10 text-center">
              <Phone className="w-8 h-8 mx-auto mb-2 text-[var(--text-muted)] opacity-30" />
              <p className="text-sm text-[var(--text-muted)]">Ingen nye opkald</p>
            </div>
          )}
        </section>

        {/* ── Kolonne 2: Under behandling ── */}
        <section className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border)] bg-amber-50 dark:bg-amber-500/10">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                <Phone className="w-4 h-4" />
                Under behandling
              </h2>
              <span className="text-2xl font-bold text-amber-700 dark:text-amber-400">{contactedCallsList.length}</span>
            </div>
          </div>
          {contactedCallsList.length > 0 ? (
            <CallLog calls={contactedCallsList} onCallUpdated={fetchData} onPushOrdrestyring={handlePushOrdrestyring} />
          ) : (
            <div className="py-10 text-center">
              <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-[var(--text-muted)] opacity-30" />
              <p className="text-sm text-[var(--text-muted)]">Ingen under behandling</p>
            </div>
          )}
        </section>

        {/* ── Kolonne 3: Færdiggjort ── */}
        <section className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border)] bg-green-50 dark:bg-green-500/10">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-green-700 dark:text-green-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                Færdiggjort
              </h2>
              <span className="text-2xl font-bold text-green-700 dark:text-green-400">{resolvedCallsList.length}</span>
            </div>
          </div>
          {resolvedCallsList.length > 0 ? (
            <CallLog calls={resolvedCallsList} onCallUpdated={fetchData} onPushOrdrestyring={handlePushOrdrestyring} />
          ) : (
            <div className="py-10 text-center">
              <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-[var(--text-muted)] opacity-30" />
              <p className="text-sm text-[var(--text-muted)]">Ingen færdiggjorte</p>
            </div>
          )}
        </section>

      </div>
    </div>
  )
}

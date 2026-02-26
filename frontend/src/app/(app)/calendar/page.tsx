'use client'

import { useState, useEffect, useCallback } from 'react'
import { Calendar, ChevronLeft, ChevronRight, Plus, X, Phone, ClipboardList, Clock } from 'lucide-react'
import { api } from '@/lib/api'

interface CalendarEvent {
  id: string
  title: string
  description: string | null
  start_time: string
  end_time: string
  event_type: string
  action_item_id: string | null
  call_id: string | null
  external_event_id: string | null
  provider: string | null
}

interface CalendarStatus {
  connected: boolean
  provider: string | null
  email: string | null
}

const EVENT_COLORS: Record<string, string> = {
  action_item: 'bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-300 border-l-2 border-blue-500',
  call: 'bg-green-100 text-green-800 dark:bg-green-500/20 dark:text-green-300 border-l-2 border-green-500',
  manual: 'bg-purple-100 text-purple-800 dark:bg-purple-500/20 dark:text-purple-300 border-l-2 border-purple-500',
}

const EVENT_ICONS: Record<string, typeof ClipboardList> = {
  action_item: ClipboardList,
  call: Phone,
  manual: Calendar,
}

function formatTime(dt: string): string {
  return new Date(dt).toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' })
}

function formatDate(dt: string): string {
  return new Date(dt).toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' })
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
}

function getDaysInMonth(year: number, month: number): Date[] {
  const days: Date[] = []
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)

  // Mandag som første ugedag
  const startDay = (first.getDay() + 6) % 7
  for (let i = startDay - 1; i >= 0; i--) {
    days.push(new Date(year, month, -i))
  }
  for (let d = 1; d <= last.getDate(); d++) {
    days.push(new Date(year, month, d))
  }
  // Udfyld resten til 6 uger
  while (days.length % 7 !== 0) {
    days.push(new Date(year, month + 1, days.length - last.getDate() - startDay + 1))
  }
  return days
}

function getWeekDays(anchor: Date): Date[] {
  const day = anchor.getDay()
  const monday = new Date(anchor)
  monday.setDate(anchor.getDate() - ((day + 6) % 7))
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    return d
  })
}

const WEEK_DAYS = ['Man', 'Tir', 'Ons', 'Tor', 'Fre', 'Lør', 'Søn']
const MONTHS = ['Januar', 'Februar', 'Marts', 'April', 'Maj', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'December']

export default function CalendarPage() {
  const [view, setView] = useState<'month' | 'week'>('month')
  const [anchor, setAnchor] = useState(new Date())
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [status, setStatus] = useState<CalendarStatus | null>(null)
  const [selected, setSelected] = useState<CalendarEvent | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [form, setForm] = useState({
    title: '',
    description: '',
    start_time: '',
    end_time: '',
  })

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    try {
      let start: Date, end: Date
      if (view === 'month') {
        start = new Date(anchor.getFullYear(), anchor.getMonth(), 1)
        end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0, 23, 59, 59)
      } else {
        const days = getWeekDays(anchor)
        start = days[0]
        end = new Date(days[6])
        end.setHours(23, 59, 59)
      }
      const data = await api.getCalendarEvents(start.toISOString(), end.toISOString())
      setEvents(data || [])
    } catch {
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [anchor, view])

  useEffect(() => {
    fetchEvents()
    api.getCalendarStatus().then(setStatus).catch(() => {})
  }, [fetchEvents])

  const navigate = (dir: number) => {
    const next = new Date(anchor)
    if (view === 'month') {
      next.setMonth(anchor.getMonth() + dir)
    } else {
      next.setDate(anchor.getDate() + dir * 7)
    }
    setAnchor(next)
  }

  const handleCreate = async () => {
    if (!form.title || !form.start_time || !form.end_time) return
    setSaving(true)
    try {
      await api.createCalendarEvent({
        title: form.title,
        description: form.description || undefined,
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
        event_type: 'manual',
      })
      setShowForm(false)
      setForm({ title: '', description: '', start_time: '', end_time: '' })
      fetchEvents()
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Slet begivenhed?')) return
    await api.deleteCalendarEvent(id)
    setSelected(null)
    fetchEvents()
  }

  const eventsForDay = (day: Date) =>
    events.filter(e => isSameDay(new Date(e.start_time), day))

  // Header tekst
  const headerText = view === 'month'
    ? `${MONTHS[anchor.getMonth()]} ${anchor.getFullYear()}`
    : (() => {
        const days = getWeekDays(anchor)
        return `Uge — ${days[0].getDate()}. ${MONTHS[days[0].getMonth()].toLowerCase()} – ${days[6].getDate()}. ${MONTHS[days[6].getMonth()].toLowerCase()} ${days[6].getFullYear()}`
      })()

  const today = new Date()

  return (
    <div className="p-6 max-w-6xl animate-fadeIn">
      {/* Topbar */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-[#42D1B9]/10">
            <Calendar className="w-5 h-5 text-[#42D1B9]" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-zinc-100">Kalender</h1>
          {status && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              status.connected
                ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300'
                : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
            }`}>
              {status.connected ? `Synkroniseret med ${status.provider === 'gmail' ? 'Google' : 'Outlook'}` : 'Ikke forbundet'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Vis/uge toggle */}
          <div className="flex rounded-lg border border-slate-200 dark:border-zinc-800 overflow-hidden">
            <button
              onClick={() => setView('month')}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                view === 'month'
                  ? 'bg-[#42D1B9]/10 text-[#162249] dark:text-[#42D1B9]'
                  : 'text-slate-500 dark:text-zinc-400 hover:bg-slate-50 dark:hover:bg-zinc-800'
              }`}
            >
              Måned
            </button>
            <button
              onClick={() => setView('week')}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                view === 'week'
                  ? 'bg-[#42D1B9]/10 text-[#162249] dark:text-[#42D1B9]'
                  : 'text-slate-500 dark:text-zinc-400 hover:bg-slate-50 dark:hover:bg-zinc-800'
              }`}
            >
              Uge
            </button>
          </div>

          {/* Navigation */}
          <button
            onClick={() => navigate(-1)}
            className="p-1.5 rounded-lg text-slate-500 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            onClick={() => setAnchor(new Date())}
            className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-zinc-800 text-slate-600 dark:text-zinc-300 hover:bg-slate-50 dark:hover:bg-zinc-800"
          >
            I dag
          </button>
          <button
            onClick={() => navigate(1)}
            className="p-1.5 rounded-lg text-slate-500 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800"
          >
            <ChevronRight className="w-5 h-5" />
          </button>

          {/* Opret knap */}
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-[#42D1B9] text-white rounded-lg hover:bg-[#38b8a2] transition-colors"
          >
            <Plus className="w-4 h-4" />
            Opret aftale
          </button>
        </div>
      </div>

      {/* Header tekst */}
      <p className="text-lg font-semibold text-slate-700 dark:text-zinc-300 mb-4 capitalize">{headerText}</p>

      {/* Kalender gitter */}
      <div className="glass-card overflow-hidden">
        {/* Ugedage header */}
        <div className="grid grid-cols-7 border-b border-slate-200 dark:border-white/[0.06]">
          {WEEK_DAYS.map(d => (
            <div key={d} className="px-2 py-3 text-center text-xs font-semibold text-slate-500 dark:text-zinc-500 uppercase tracking-wide">
              {d}
            </div>
          ))}
        </div>

        {view === 'month' ? (
          /* Månedsvisning */
          <div className="grid grid-cols-7">
            {getDaysInMonth(anchor.getFullYear(), anchor.getMonth()).map((day, i) => {
              const isCurrentMonth = day.getMonth() === anchor.getMonth()
              const isToday = isSameDay(day, today)
              const dayEvents = eventsForDay(day)

              return (
                <div
                  key={i}
                  className={`min-h-[100px] p-2 border-b border-r border-slate-100 dark:border-white/[0.04] ${
                    i % 7 === 6 ? 'border-r-0' : ''
                  } ${!isCurrentMonth ? 'bg-slate-50/50 dark:bg-zinc-900/30' : ''}`}
                >
                  <span className={`inline-flex items-center justify-center w-7 h-7 text-sm rounded-full mb-1 font-medium ${
                    isToday
                      ? 'bg-[#42D1B9] text-white'
                      : isCurrentMonth
                        ? 'text-slate-700 dark:text-zinc-300'
                        : 'text-slate-300 dark:text-zinc-600'
                  }`}>
                    {day.getDate()}
                  </span>

                  <div className="space-y-0.5">
                    {dayEvents.slice(0, 3).map(ev => {
                      const Icon = EVENT_ICONS[ev.event_type] || Calendar
                      return (
                        <button
                          key={ev.id}
                          onClick={() => setSelected(ev)}
                          className={`w-full text-left px-1.5 py-0.5 rounded text-xs truncate flex items-center gap-1 ${EVENT_COLORS[ev.event_type] || EVENT_COLORS.manual}`}
                        >
                          <Icon className="w-3 h-3 flex-shrink-0" />
                          <span className="truncate">{ev.title}</span>
                        </button>
                      )
                    })}
                    {dayEvents.length > 3 && (
                      <p className="text-xs text-slate-400 dark:text-zinc-500 pl-1">+{dayEvents.length - 3} mere</p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          /* Ugevisning */
          <div className="grid grid-cols-7 divide-x divide-slate-100 dark:divide-white/[0.04]">
            {getWeekDays(anchor).map((day, i) => {
              const isToday = isSameDay(day, today)
              const dayEvents = eventsForDay(day)

              return (
                <div key={i} className="min-h-[400px] p-2">
                  <div className={`text-center mb-3 pb-2 border-b border-slate-100 dark:border-white/[0.04]`}>
                    <p className="text-xs text-slate-500 dark:text-zinc-500 uppercase">{WEEK_DAYS[i]}</p>
                    <span className={`inline-flex items-center justify-center w-8 h-8 text-sm rounded-full font-semibold mt-1 ${
                      isToday ? 'bg-[#42D1B9] text-white' : 'text-slate-700 dark:text-zinc-300'
                    }`}>
                      {day.getDate()}
                    </span>
                  </div>

                  <div className="space-y-1">
                    {dayEvents.map(ev => {
                      const Icon = EVENT_ICONS[ev.event_type] || Calendar
                      return (
                        <button
                          key={ev.id}
                          onClick={() => setSelected(ev)}
                          className={`w-full text-left px-2 py-1.5 rounded-md text-xs ${EVENT_COLORS[ev.event_type] || EVENT_COLORS.manual}`}
                        >
                          <div className="flex items-center gap-1 mb-0.5">
                            <Icon className="w-3 h-3 flex-shrink-0" />
                            <span className="font-medium truncate">{ev.title}</span>
                          </div>
                          <div className="flex items-center gap-1 text-xs opacity-70">
                            <Clock className="w-2.5 h-2.5" />
                            {formatTime(ev.start_time)}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {loading && (
        <p className="text-center text-sm text-slate-400 dark:text-zinc-600 mt-4">Henter begivenheder...</p>
      )}

      {/* Farve-legende */}
      <div className="flex items-center gap-4 mt-4 text-xs text-slate-500 dark:text-zinc-500">
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-blue-400" /> Action items</div>
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-green-400" /> Opkald</div>
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-purple-400" /> Manuel aftale</div>
      </div>

      {/* Event detalje popup */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm" onClick={() => setSelected(null)}>
          <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  {(() => { const Icon = EVENT_ICONS[selected.event_type] || Calendar; return <Icon className="w-4 h-4 text-[#42D1B9]" /> })()}
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-zinc-100">{selected.title}</h2>
                </div>
                <p className="text-sm text-slate-500 dark:text-zinc-400">{formatDate(selected.start_time)}</p>
                <p className="text-sm text-slate-500 dark:text-zinc-400">{formatTime(selected.start_time)} – {formatTime(selected.end_time)}</p>
              </div>
              <button onClick={() => setSelected(null)} className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800">
                <X className="w-4 h-4" />
              </button>
            </div>

            {selected.description && (
              <p className="text-sm text-slate-600 dark:text-zinc-400 mb-4 bg-slate-50 dark:bg-zinc-800/50 rounded-lg p-3">{selected.description}</p>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {selected.external_event_id && (
                  <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300 rounded-full">
                    Synkroniseret
                  </span>
                )}
                {selected.action_item_id && (
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300 rounded-full">
                    Action item
                  </span>
                )}
                {selected.call_id && (
                  <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300 rounded-full">
                    Opkald
                  </span>
                )}
              </div>
              {selected.event_type === 'manual' && (
                <button
                  onClick={() => handleDelete(selected.id)}
                  className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400 px-3 py-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                >
                  Slet
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Opret formular */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm" onClick={() => setShowForm(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-zinc-100">Opret aftale</h2>
              <button onClick={() => setShowForm(false)} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-zinc-300 mb-1.5">Titel</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="Møde med kunde..."
                  className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-[#42D1B9]/50 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-zinc-300 mb-1.5">Beskrivelse (valgfri)</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  rows={2}
                  className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-[#42D1B9]/50 outline-none resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-zinc-300 mb-1.5">Start</label>
                  <input
                    type="datetime-local"
                    value={form.start_time}
                    onChange={e => setForm(f => ({ ...f, start_time: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-[#42D1B9]/50 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-zinc-300 mb-1.5">Slut</label>
                  <input
                    type="datetime-local"
                    value={form.end_time}
                    onChange={e => setForm(f => ({ ...f, end_time: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-[#42D1B9]/50 outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors"
                >
                  Annuller
                </button>
                <button
                  onClick={handleCreate}
                  disabled={saving || !form.title || !form.start_time || !form.end_time}
                  className="px-4 py-2 text-sm font-medium bg-[#42D1B9] text-white rounded-lg hover:bg-[#38b8a2] disabled:opacity-50 transition-colors"
                >
                  {saving ? 'Opretter...' : 'Opret'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

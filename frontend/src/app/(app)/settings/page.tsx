'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Settings, Mail, Trash2, LogOut, Globe, Moon, Sun, Calendar, CheckCircle2 } from 'lucide-react'
import { useTranslation, Locale } from '@/lib/i18n'

interface Account {
  id: string
  provider: string
  email_address: string
  is_active: boolean
  created_at: string
}

interface CalendarAccount {
  id: string
  provider: string
  calendar_email: string
  is_active: boolean
  created_at: string
}

export default function SettingsPage() {
  const { t, locale, setLocale, theme, setTheme } = useTranslation()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [calendarAccounts, setCalendarAccounts] = useState<CalendarAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [connectingCalendar, setConnectingCalendar] = useState(false)

  const fetchAccounts = async () => {
    try {
      const data = await api.listAccounts()
      setAccounts(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const fetchCalendarAccounts = async () => {
    try {
      const data = await api.listCalendarAccounts()
      setCalendarAccounts(data || [])
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    fetchAccounts()
    fetchCalendarAccounts()
  }, [])

  const handleConnect = async (provider: 'gmail' | 'outlook') => {
    setConnecting(true)
    try {
      const fn = provider === 'gmail' ? api.connectGmail : api.connectOutlook
      const data = await fn()
      window.open(data.auth_url, '_blank')
    } catch (err) {
      console.error(err)
    } finally {
      setConnecting(false)
    }
  }

  const handleConnectCalendar = async (provider: 'google' | 'outlook') => {
    setConnectingCalendar(true)
    try {
      const fn = provider === 'google' ? api.connectGoogleCalendar : api.connectOutlookCalendar
      const data = await fn()
      window.open(data.auth_url, '_blank')
    } catch (err) {
      console.error(err)
    } finally {
      setConnectingCalendar(false)
    }
  }

  const handleDisconnect = async (id: string) => {
    if (!confirm(t('disconnectAccount'))) return
    await api.disconnectAccount(id)
    fetchAccounts()
  }

  const handleDisconnectCalendar = async (id: string) => {
    if (!confirm(t('disconnectCalendar'))) return
    await api.deleteCalendarAccount(id)
    fetchCalendarAccounts()
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    window.location.href = '/login'
  }

  return (
    <div className="p-8 max-w-3xl animate-fadeIn">
      <div className="flex items-center gap-2.5 mb-6">
        <div className="p-1.5 rounded-lg bg-[#42D1B9]/10">
          <Settings className="w-5 h-5 text-[#42D1B9]" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-zinc-100">{t('settings')}</h1>
      </div>

      {/* Theme selector */}
      <div className="glass-card mb-6 overflow-hidden">
        <div className="p-6 border-b border-slate-200 dark:border-white/[0.06]">
          <div className="flex items-center gap-2">
            {theme === 'light' ? <Sun className="w-5 h-5 text-amber-500" /> : <Moon className="w-5 h-5 text-[#42D1B9]" />}
            <h2 className="text-lg font-semibold text-slate-900 dark:text-zinc-100">{t('theme')}</h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-zinc-500 mt-1">{t('themeDesc')}</p>
        </div>
        <div className="p-6">
          <div className="flex gap-3">
            <button
              onClick={() => setTheme('light')}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border rounded-lg transition-all ${
                theme === 'light'
                  ? 'bg-amber-50 dark:bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-500/30'
                  : 'text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700 hover:text-slate-700 dark:hover:text-zinc-200'
              }`}
            >
              <Sun className="w-4 h-4" /> {t('themeDay')}
            </button>
            <button
              onClick={() => setTheme('dark')}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border rounded-lg transition-all ${
                theme === 'dark'
                  ? 'bg-[#42D1B9]/10 text-[#162249] dark:text-[#42D1B9] border-[#42D1B9]/30'
                  : 'text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700 hover:text-slate-700 dark:hover:text-zinc-200'
              }`}
            >
              <Moon className="w-4 h-4" /> {t('themeNight')}
            </button>
          </div>
        </div>
      </div>

      {/* Language selector */}
      <div className="glass-card mb-6 overflow-hidden">
        <div className="p-6 border-b border-slate-200 dark:border-white/[0.06]">
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-[#42D1B9]" />
            <h2 className="text-lg font-semibold text-slate-900 dark:text-zinc-100">{t('language')}</h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-zinc-500 mt-1">{t('languageDesc')}</p>
        </div>
        <div className="p-6">
          <div className="flex gap-3">
            <button
              onClick={() => setLocale('da')}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border rounded-lg transition-all ${
                locale === 'da'
                  ? 'bg-[#42D1B9]/10 text-[#162249] dark:text-[#42D1B9] border-[#42D1B9]/30'
                  : 'text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700 hover:text-slate-700 dark:hover:text-zinc-200'
              }`}
            >
              <span className="text-lg">🇩🇰</span> Dansk
            </button>
            <button
              onClick={() => setLocale('en')}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border rounded-lg transition-all ${
                locale === 'en'
                  ? 'bg-[#42D1B9]/10 text-[#162249] dark:text-[#42D1B9] border-[#42D1B9]/30'
                  : 'text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700 hover:text-slate-700 dark:hover:text-zinc-200'
              }`}
            >
              <span className="text-lg">🇬🇧</span> English
            </button>
          </div>
        </div>
      </div>

      {/* Connected accounts */}
      <div className="glass-card mb-6 overflow-hidden">
        <div className="p-6 border-b border-slate-200 dark:border-white/[0.06]">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-zinc-100">{t('emailAccounts')}</h2>
          <p className="text-sm text-slate-500 dark:text-zinc-500 mt-1">{t('emailAccountsDesc')}</p>
        </div>

        <div className="p-6">
          {loading ? (
            <p className="text-slate-400 dark:text-zinc-600 text-sm">{t('loading')}</p>
          ) : (
            <>
              {accounts.length > 0 && (
                <div className="space-y-3 mb-6">
                  {accounts.map((acc) => (
                    <div key={acc.id} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-zinc-900/50 rounded-lg border border-slate-200 dark:border-white/[0.04]">
                      <div className="flex items-center gap-3">
                        <Mail className="w-5 h-5 text-slate-400 dark:text-zinc-500" />
                        <div>
                          <p className="text-sm font-medium text-slate-800 dark:text-zinc-200">{acc.email_address}</p>
                          <p className="text-xs text-slate-500 dark:text-zinc-500 capitalize">{acc.provider}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${acc.is_active ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]' : 'bg-slate-300 dark:bg-zinc-600'}`} />
                        <button
                          onClick={() => handleDisconnect(acc.id)}
                          className="p-1.5 text-slate-400 dark:text-zinc-600 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => handleConnect('gmail')}
                  disabled={connecting}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-slate-200 dark:border-zinc-800 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-800/50 hover:border-slate-300 dark:hover:border-zinc-700 disabled:opacity-50 text-slate-700 dark:text-zinc-300 transition-all"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#EA4335" d="M5.266 9.765A7.077 7.077 0 0 1 12 4.909c1.69 0 3.218.6 4.418 1.582L19.91 3C17.782 1.145 15.055 0 12 0 7.27 0 3.198 2.698 1.24 6.65l4.026 3.115Z"/><path fill="#34A853" d="M16.04 18.013c-1.09.703-2.474 1.078-4.04 1.078a7.077 7.077 0 0 1-6.723-4.823l-4.04 3.067A11.965 11.965 0 0 0 12 24c2.933 0 5.735-1.043 7.834-3l-3.793-2.987Z"/><path fill="#4A90D9" d="M19.834 21c2.195-2.048 3.62-5.096 3.62-9 0-.71-.109-1.473-.272-2.182H12v4.637h6.436c-.317 1.559-1.17 2.766-2.395 3.558L19.834 21Z"/><path fill="#FBBC05" d="M5.277 14.268A7.12 7.12 0 0 1 4.909 12c0-.782.125-1.533.357-2.235L1.24 6.65A11.934 11.934 0 0 0 0 12c0 1.92.445 3.73 1.237 5.335l4.04-3.067Z"/></svg>
                  {t('connectGmail')}
                </button>
                <button
                  onClick={() => handleConnect('outlook')}
                  disabled={connecting}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-slate-200 dark:border-zinc-800 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-800/50 hover:border-slate-300 dark:hover:border-zinc-700 disabled:opacity-50 text-slate-700 dark:text-zinc-300 transition-all"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#0078D4" d="M24 7.387v10.478c0 .23-.08.424-.238.58a.782.782 0 0 1-.578.236h-8.307v-8.16l1.87 1.358a.327.327 0 0 0 .39 0l6.863-4.973V7.387Zm-9.123-1.39h8.307c.224 0 .414.076.57.228.155.152.236.34.246.564l-7.286 5.282-1.837-1.334V5.997ZM13.543 3v18L0 18.246V2.754L13.543 3Z"/><ellipse cx="6.772" cy="11.641" fill="#0078D4" rx="3.5" ry="4.5"/></svg>
                  {t('connectOutlook')}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Kalender integration */}
      <div className="glass-card mb-6 overflow-hidden">
        <div className="p-6 border-b border-slate-200 dark:border-white/[0.06]">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[#42D1B9]" />
            <h2 className="text-lg font-semibold text-slate-900 dark:text-zinc-100">{t('calendarIntegration')}</h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-zinc-500 mt-1">
            {t('calendarIntegrationDesc')}
          </p>
        </div>

        <div className="p-6">
          {/* Tilsluttede kalenderkonti */}
          {calendarAccounts.length > 0 && (
            <div className="space-y-3 mb-6">
              {calendarAccounts.map((acc) => (
                <div key={acc.id} className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-500/10 rounded-lg border border-green-200 dark:border-green-500/20">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-green-800 dark:text-green-300">
                        {acc.calendar_email}
                      </p>
                      <p className="text-xs text-green-600 dark:text-green-400 capitalize">
                        {acc.provider === 'google' ? 'Google Kalender' : 'Outlook Kalender'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${acc.is_active ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]' : 'bg-slate-300 dark:bg-zinc-600'}`} />
                    <button
                      onClick={() => handleDisconnectCalendar(acc.id)}
                      className="p-1.5 text-slate-400 dark:text-zinc-600 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {calendarAccounts.length === 0 && (
            <p className="text-sm text-slate-500 dark:text-zinc-500 mb-4">
              {t('calendarNotConnectedDesc')}
            </p>
          )}

          <div className="flex gap-3 flex-wrap">
            <button
              onClick={() => handleConnectCalendar('google')}
              disabled={connectingCalendar}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-slate-200 dark:border-zinc-800 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-800/50 hover:border-slate-300 dark:hover:border-zinc-700 disabled:opacity-50 text-slate-700 dark:text-zinc-300 transition-all"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#EA4335" d="M5.266 9.765A7.077 7.077 0 0 1 12 4.909c1.69 0 3.218.6 4.418 1.582L19.91 3C17.782 1.145 15.055 0 12 0 7.27 0 3.198 2.698 1.24 6.65l4.026 3.115Z"/><path fill="#34A853" d="M16.04 18.013c-1.09.703-2.474 1.078-4.04 1.078a7.077 7.077 0 0 1-6.723-4.823l-4.04 3.067A11.965 11.965 0 0 0 12 24c2.933 0 5.735-1.043 7.834-3l-3.793-2.987Z"/><path fill="#4A90D9" d="M19.834 21c2.195-2.048 3.62-5.096 3.62-9 0-.71-.109-1.473-.272-2.182H12v4.637h6.436c-.317 1.559-1.17 2.766-2.395 3.558L19.834 21Z"/><path fill="#FBBC05" d="M5.277 14.268A7.12 7.12 0 0 1 4.909 12c0-.782.125-1.533.357-2.235L1.24 6.65A11.934 11.934 0 0 0 0 12c0 1.92.445 3.73 1.237 5.335l4.04-3.067Z"/></svg>
              {t('connectGoogleCalendar')}
            </button>
            <button
              onClick={() => handleConnectCalendar('outlook')}
              disabled={connectingCalendar}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-slate-200 dark:border-zinc-800 rounded-lg hover:bg-slate-50 dark:hover:bg-zinc-800/50 hover:border-slate-300 dark:hover:border-zinc-700 disabled:opacity-50 text-slate-700 dark:text-zinc-300 transition-all"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#0078D4" d="M24 7.387v10.478c0 .23-.08.424-.238.58a.782.782 0 0 1-.578.236h-8.307v-8.16l1.87 1.358a.327.327 0 0 0 .39 0l6.863-4.973V7.387Zm-9.123-1.39h8.307c.224 0 .414.076.57.228.155.152.236.34.246.564l-7.286 5.282-1.837-1.334V5.997ZM13.543 3v18L0 18.246V2.754L13.543 3Z"/></svg>
              {t('connectOutlookCalendar')}
            </button>
          </div>
        </div>
      </div>

      {/* Logout */}
      <div className="glass-card p-6">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 px-4 py-2 text-sm text-red-500 dark:text-red-400 border border-red-200 dark:border-red-500/20 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 transition-all"
        >
          <LogOut className="w-4 h-4" /> {t('signOut')}
        </button>
      </div>
    </div>
  )
}

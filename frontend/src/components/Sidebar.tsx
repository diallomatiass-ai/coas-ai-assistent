'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import Image from 'next/image'
import { useEffect, useState } from 'react'
import { Inbox, LayoutDashboard, FileText, BookOpen, Settings, Sun, Moon, Phone, Users, Calendar, ShieldCheck, CreditCard } from 'lucide-react'
import { useTranslation } from '@/lib/i18n'
import { api } from '@/lib/api'

interface BadgeCounts {
  unread: number
  newCalls: number
  overdueTasks: number
  todayEvents: number
}

interface CurrentUser {
  id: string
  role: string
  name: string
  email: string
}

export default function Sidebar() {
  const pathname = usePathname()
  const { t, theme, setTheme } = useTranslation()
  const [badges, setBadges] = useState<BadgeCounts>({ unread: 0, newCalls: 0, overdueTasks: 0, todayEvents: 0 })
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)

  useEffect(() => {
    // Hent brugerinfo (til admin-check)
    api.getMe().then((u: CurrentUser) => setCurrentUser(u)).catch(() => null)
  }, [])

  useEffect(() => {
    // Hent badge counts
    const todayStart = new Date(); todayStart.setHours(0, 0, 0, 0)
    const todayEnd = new Date(); todayEnd.setHours(23, 59, 59, 999)

    Promise.all([
      api.getDashboardSummary().catch(() => null),
      api.getCallDashboard().catch(() => null),
      api.getReminderCount().catch(() => null),
      api.getCalendarEvents(todayStart.toISOString(), todayEnd.toISOString()).catch(() => null),
    ]).then(([dash, calls, reminderData, calEvents]) => {
      const reminderCount = reminderData?.count ?? 0
      setBadges({
        unread: (dash?.unread ?? 0) + reminderCount,
        newCalls: calls?.new_calls ?? 0,
        overdueTasks: 0,
        todayEvents: Array.isArray(calEvents) ? calEvents.length : 0,
      })
    })
  }, [pathname]) // Refresh on navigation

  const navItems = [
    { href: '/', label: t('dashboard'), icon: LayoutDashboard, badge: 0 },
    { href: '/inbox', label: t('inbox'), icon: Inbox, badge: badges.unread },
    { href: '/ai-secretary', label: t('aiSecretary'), icon: Phone, badge: badges.newCalls },
    { href: '/customers', label: t('customers'), icon: Users, badge: 0 },
    { href: '/calendar', label: 'Kalender', icon: Calendar, badge: badges.todayEvents },
    { href: '/templates', label: t('templates'), icon: FileText, badge: 0 },
    { href: '/knowledge', label: t('knowledgeBase'), icon: BookOpen, badge: 0 },
    { href: '/settings', label: t('settings'), icon: Settings, badge: 0 },
    { href: '/billing', label: 'Abonnement', icon: CreditCard, badge: 0 },
    ...(currentUser?.role === 'admin'
      ? [{ href: '/admin', label: 'Admin', icon: ShieldCheck, badge: 0 }]
      : []),
  ]

  // Mobil bottom-nav: kun de 4 vigtigste
  const mobileItems = navItems.slice(0, 4)

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 border-r border-[var(--border)] bg-[var(--surface)] flex-col">
        <div className="px-4 py-5 border-b border-[var(--border)]">
          <div className="flex items-center justify-center">
            <Image
              src={theme === 'dark' ? '/logo-dark.png' : '/logo.png'}
              alt="Ahmes"
              width={150}
              height={90}
              className="object-contain"
            />
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href ||
              (item.href !== '/' && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[#42D1B9]/10 text-[#162249] dark:text-[#42D1B9]'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Icon className={`w-6 h-6 ${isActive ? 'text-[#42D1B9]' : ''}`} />
                <span className="flex-1">{item.label}</span>
                {item.badge > 0 && (
                  <span className="min-w-[22px] h-[22px] flex items-center justify-center rounded-full bg-red-600 text-white text-xs font-bold px-1.5">
                    {item.badge > 99 ? '99+' : item.badge}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>
        <div className="p-3 border-t border-[var(--border)]">
          <button
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            className="flex items-center gap-2 w-full px-3 py-2.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] rounded-lg hover:bg-[var(--surface-hover)] transition-colors"
          >
            {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
            {theme === 'light' ? t('themeNight') : t('themeDay')}
          </button>
        </div>
      </aside>

      {/* Mobil bottom navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[var(--surface)] border-t border-[var(--border)] safe-area-bottom">
        <div className="flex justify-around items-center h-16">
          {mobileItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href ||
              (item.href !== '/' && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full relative ${
                  isActive
                    ? 'text-[#42D1B9]'
                    : 'text-[var(--text-muted)]'
                }`}
              >
                <div className="relative">
                  <Icon className="w-6 h-6" />
                  {item.badge > 0 && (
                    <span className="absolute -top-1.5 -right-2.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-600 text-white text-[10px] font-bold px-1">
                      {item.badge > 99 ? '99+' : item.badge}
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-medium">{item.label}</span>
              </Link>
            )
          })}
        </div>
      </nav>
    </>
  )
}

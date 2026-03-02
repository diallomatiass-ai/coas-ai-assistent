'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useSearchParams } from 'next/navigation'
import {
  CreditCard, CheckCircle2, Zap, Star, Building2,
  ExternalLink, Loader2, AlertCircle, Gift
} from 'lucide-react'

interface Plan {
  id: string
  label: string
  price_dkk: number
  features: string[]
}

interface Subscription {
  plan: string
  status: string
  label: string
  price_dkk: number
  features: string[]
  trial_ends_at: string | null
  subscription_ends_at: string | null
  stripe_customer_id: string | null
  has_active_subscription: boolean
}

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free:     <Gift className="w-6 h-6" />,
  starter:  <Zap className="w-6 h-6" />,
  pro:      <Star className="w-6 h-6" />,
  business: <Building2 className="w-6 h-6" />,
}

const PLAN_COLORS: Record<string, string> = {
  free:     'border-gray-200 dark:border-gray-700',
  starter:  'border-blue-400',
  pro:      'border-[#42D1B9] ring-2 ring-[#42D1B9]/30',
  business: 'border-purple-500',
}

const PLAN_BADGE: Record<string, string | null> = {
  free:     null,
  starter:  null,
  pro:      'Mest populær',
  business: null,
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  free:      { label: 'Gratis', color: 'text-gray-500' },
  trialing:  { label: '14 dages gratis prøve', color: 'text-blue-600' },
  active:    { label: 'Aktivt', color: 'text-green-600' },
  past_due:  { label: 'Betaling fejlet', color: 'text-red-600' },
  canceled:  { label: 'Annulleret', color: 'text-gray-500' },
}

export default function BillingPage() {
  const searchParams = useSearchParams()
  const [plans, setPlans] = useState<Plan[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(true)
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null)
  const [portalLoading, setPortalLoading] = useState(false)
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null)

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => {
    const success = searchParams.get('success')
    const canceled = searchParams.get('canceled')
    if (success) showToast('Betaling gennemført — dit abonnement er aktivt!')
    if (canceled) showToast('Checkout annulleret — du er ikke blevet opkrævet.', 'error')
  }, [searchParams])

  useEffect(() => {
    Promise.all([api.getBillingPlans(), api.getSubscription()])
      .then(([p, s]) => {
        setPlans(p)
        setSubscription(s)
      })
      .catch(() => showToast('Kunne ikke hente abonnementsinformation', 'error'))
      .finally(() => setLoading(false))
  }, [])

  const handleCheckout = async (planId: string) => {
    if (planId === 'free') return
    setCheckoutLoading(planId)
    try {
      const { url } = await api.createCheckout(planId)
      window.location.href = url
    } catch (err: any) {
      showToast(err.message || 'Stripe ikke konfigureret endnu', 'error')
    } finally {
      setCheckoutLoading(null)
    }
  }

  const handlePortal = async () => {
    setPortalLoading(true)
    try {
      const { url } = await api.createPortal()
      window.location.href = url
    } catch (err: any) {
      showToast(err.message || 'Kunne ikke åbne fakturaportalen', 'error')
    } finally {
      setPortalLoading(false)
    }
  }

  const fmtDate = (iso: string | null) => {
    if (!iso) return null
    return new Date(iso).toLocaleDateString('da-DK', { day: 'numeric', month: 'long', year: 'numeric' })
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#42D1B9]" />
      </div>
    )
  }

  const currentPlan = subscription?.plan || 'free'
  const currentStatus = subscription?.status || 'free'
  const statusInfo = STATUS_LABELS[currentStatus] || STATUS_LABELS.free

  return (
    <div className="flex-1 overflow-auto p-4 md:p-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg text-white text-sm font-medium
          ${toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>
          {toast.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          {toast.msg}
        </div>
      )}

      <div className="max-w-5xl mx-auto space-y-8">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <CreditCard className="w-7 h-7 text-[#42D1B9]" />
            Abonnement & Betaling
          </h1>
          <p className="text-[var(--text-secondary)] mt-1">
            Vælg den plan der passer til din virksomhed. 14 dages gratis prøveperiode uden kreditkort.
          </p>
        </div>

        {/* Nuværende abonnement */}
        {subscription && (
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5">
            <h2 className="font-semibold text-[var(--text-primary)] mb-3">Nuværende abonnement</h2>
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#42D1B9]/10 text-[#42D1B9]">
                  {PLAN_ICONS[currentPlan]}
                </div>
                <div>
                  <div className="font-bold text-[var(--text-primary)]">{subscription.label}</div>
                  <div className={`text-sm font-medium ${statusInfo.color}`}>{statusInfo.label}</div>
                </div>
              </div>

              {subscription.trial_ends_at && (
                <div className="text-sm text-blue-600 bg-blue-50 dark:bg-blue-900/20 px-3 py-1.5 rounded-lg">
                  Prøveperiode slutter: {fmtDate(subscription.trial_ends_at)}
                </div>
              )}
              {subscription.subscription_ends_at && currentStatus !== 'trialing' && (
                <div className="text-sm text-gray-500 text-sm">
                  Fornyes: {fmtDate(subscription.subscription_ends_at)}
                </div>
              )}

              {subscription.has_active_subscription && (
                <button
                  onClick={handlePortal}
                  disabled={portalLoading}
                  className="ml-auto flex items-center gap-2 px-4 py-2 text-sm font-medium border border-[var(--border)] rounded-xl hover:bg-[var(--surface-hover)] transition-colors"
                >
                  {portalLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
                  Administrer / Fakturaer
                </button>
              )}
            </div>

            {currentStatus === 'past_due' && (
              <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-xl text-red-700 dark:text-red-400 text-sm">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                Seneste betaling fejlede. Opdater din betalingsmetode via fakturaportalen for at undgå afbrydelse.
              </div>
            )}
          </div>
        )}

        {/* Prisplaner */}
        <div>
          <h2 className="font-semibold text-[var(--text-primary)] mb-4">Vælg plan</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {plans.map((plan) => {
              const isCurrent = plan.id === currentPlan
              const badge = PLAN_BADGE[plan.id]
              const isLoading = checkoutLoading === plan.id

              return (
                <div
                  key={plan.id}
                  className={`relative flex flex-col bg-[var(--surface)] border-2 rounded-2xl p-5 transition-all
                    ${PLAN_COLORS[plan.id]}
                    ${isCurrent ? 'opacity-90' : 'hover:shadow-md'}`}
                >
                  {badge && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#42D1B9] text-white text-xs font-bold px-3 py-1 rounded-full">
                      {badge}
                    </div>
                  )}

                  <div className="flex items-center gap-2 mb-3">
                    <div className={`p-1.5 rounded-lg ${
                      plan.id === 'pro' ? 'bg-[#42D1B9]/10 text-[#42D1B9]' :
                      plan.id === 'business' ? 'bg-purple-100 text-purple-600 dark:bg-purple-900/20' :
                      plan.id === 'starter' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/20' :
                      'bg-gray-100 text-gray-500 dark:bg-gray-800'
                    }`}>
                      {PLAN_ICONS[plan.id]}
                    </div>
                    <div className="font-bold text-[var(--text-primary)]">{plan.label}</div>
                  </div>

                  <div className="mb-4">
                    {plan.price_dkk === 0 ? (
                      <div className="text-2xl font-bold text-[var(--text-primary)]">Gratis</div>
                    ) : (
                      <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-[var(--text-primary)]">{plan.price_dkk}</span>
                        <span className="text-sm text-[var(--text-secondary)]">kr/md</span>
                      </div>
                    )}
                  </div>

                  <ul className="space-y-1.5 mb-5 flex-1">
                    {plan.features.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                        <CheckCircle2 className="w-4 h-4 text-[#42D1B9] flex-shrink-0 mt-0.5" />
                        {f}
                      </li>
                    ))}
                  </ul>

                  {isCurrent ? (
                    <div className="w-full text-center py-2 text-sm font-medium text-[#42D1B9] border border-[#42D1B9]/30 rounded-xl bg-[#42D1B9]/5">
                      Nuværende plan
                    </div>
                  ) : plan.id === 'free' ? (
                    <div className="w-full text-center py-2 text-sm text-[var(--text-muted)] border border-[var(--border)] rounded-xl">
                      Gratis for altid
                    </div>
                  ) : (
                    <button
                      onClick={() => handleCheckout(plan.id)}
                      disabled={isLoading}
                      className={`w-full py-2 rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2
                        ${plan.id === 'pro'
                          ? 'bg-[#42D1B9] text-white hover:bg-[#38b9a3] shadow-sm'
                          : 'bg-[var(--text-primary)] text-[var(--bg)] hover:opacity-90'
                        }
                        disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                      {currentPlan === 'free' ? 'Start gratis prøve' : 'Skift til denne plan'}
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Info-boks */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 text-sm text-[var(--text-secondary)] space-y-2">
          <div className="font-semibold text-[var(--text-primary)]">Om abonnementer</div>
          <ul className="space-y-1 list-disc list-inside">
            <li>14 dages gratis prøveperiode — intet kreditkort kræves ved opstart</li>
            <li>Månedlig fakturering — annuller når som helst via fakturaportalen</li>
            <li>Priserne er ekskl. moms (25% moms tillægges ved fakturering)</li>
            <li>Betalingsmetoder: Dankort, Visa, Mastercard, MobilePay</li>
            <li>Spørgsmål? Skriv til <strong>support@coas.dk</strong></li>
          </ul>
        </div>
      </div>
    </div>
  )
}

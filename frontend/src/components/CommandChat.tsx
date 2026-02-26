'use client'

import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, Check, XCircle, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  requiresConfirmation?: boolean
  pendingAction?: Record<string, unknown>
  actionsTaken?: string[]
  status?: 'success' | 'warning' | 'error'
}

let msgId = 0

export default function CommandChat() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: 'assistant',
      content: 'Hej! Hvad kan jeg hjælpe med?\n\n📅 "Hvad har jeg på kalenderen i dag?"\n📋 "Vis mine forfaldne opgaver"\n📞 "Marker opkaldet fra Henrik som løst"\n📊 "Giv mig et dagsoverblik"\n✉️ "Slet alle spam-emails"\n🗓️ "Book møde med Lars fredag kl. 10"',
    },
  ])
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  const addMessage = (msg: Omit<Message, 'id'>) => {
    const id = ++msgId
    setMessages((prev) => [...prev, { ...msg, id }])
    return id
  }

  const sendMessage = async (text: string, confirm = false, pendingAction?: Record<string, unknown>) => {
    if (!text.trim() && !confirm) return
    setLoading(true)

    if (!confirm) {
      addMessage({ role: 'user', content: text })
      setInput('')
    }

    try {
      const res = await api.sendCommand(text, confirm, pendingAction)
      addMessage({
        role: 'assistant',
        content: res.response,
        requiresConfirmation: res.requires_confirmation,
        pendingAction: res.pending_action,
        actionsTaken: res.actions_taken,
        status: res.actions_taken?.length > 0 ? 'success' : undefined,
      })
    } catch (err) {
      addMessage({
        role: 'assistant',
        content: `Fejl: ${err instanceof Error ? err.message : 'Noget gik galt'}`,
        status: 'error',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = (msg: Message) => {
    addMessage({ role: 'user', content: 'Ja, bekræft' })
    sendMessage(msg.content, true, msg.pendingAction)
  }

  const handleCancel = (msgId: number) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId ? { ...m, requiresConfirmation: false, content: m.content + '\n\n*(Annulleret)*' } : m
      )
    )
    addMessage({ role: 'assistant', content: 'Handling annulleret.' })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <>
      {/* Flydende knap */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-[#162249] hover:bg-[#1e2d6b] text-white shadow-lg shadow-[#162249]/30 flex items-center justify-center transition-all duration-200 hover:scale-110"
          title="AI Chat"
        >
          <MessageSquare className="w-6 h-6" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-96 h-[560px] flex flex-col rounded-2xl shadow-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-white/[0.08] overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-[#162249] text-white">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5" />
              <span className="font-semibold text-sm">AI Kommandochat</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="hover:bg-[#1e2d6b] rounded-lg p-1 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Beskeder */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                    msg.role === 'user'
                      ? 'bg-[#162249] text-white rounded-br-sm'
                      : msg.status === 'success'
                      ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-bl-sm'
                      : msg.status === 'error'
                      ? 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800 rounded-bl-sm'
                      : msg.requiresConfirmation
                      ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 rounded-bl-sm'
                      : 'bg-slate-100 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 rounded-bl-sm'
                  }`}
                >
                  {msg.content}

                  {/* Udførte handlinger */}
                  {msg.actionsTaken && msg.actionsTaken.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-emerald-200 dark:border-emerald-700 text-xs opacity-80">
                      {msg.actionsTaken.map((a, i) => (
                        <div key={i} className="flex items-center gap-1">
                          <Check className="w-3 h-3" /> {a}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Bekræftelsesknapper */}
                  {msg.requiresConfirmation && msg.pendingAction && (
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => handleConfirm(msg)}
                        disabled={loading}
                        className="flex items-center gap-1 px-3 py-1.5 bg-[#42D1B9] hover:bg-[#2ABBA4] text-[#0D1B3E] text-xs rounded-lg font-medium transition-colors disabled:opacity-50"
                      >
                        <Check className="w-3 h-3" /> Ja, udfør
                      </button>
                      <button
                        onClick={() => handleCancel(msg.id)}
                        disabled={loading}
                        className="flex items-center gap-1 px-3 py-1.5 bg-slate-200 dark:bg-zinc-700 hover:bg-slate-300 dark:hover:bg-zinc-600 text-slate-700 dark:text-zinc-300 text-xs rounded-lg font-medium transition-colors disabled:opacity-50"
                      >
                        <XCircle className="w-3 h-3" /> Annuller
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-slate-100 dark:bg-zinc-800 rounded-2xl rounded-bl-sm px-4 py-3">
                  <Loader2 className="w-4 h-4 animate-spin text-[#42D1B9]" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-slate-200 dark:border-white/[0.08]">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Skriv en kommando..."
                rows={1}
                disabled={loading}
                className="flex-1 resize-none rounded-xl border border-slate-200 dark:border-white/[0.1] bg-slate-50 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 text-sm px-3 py-2 placeholder-slate-400 dark:placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-[#42D1B9] disabled:opacity-50"
                style={{ maxHeight: '100px' }}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={loading || !input.trim()}
                className="w-9 h-9 flex items-center justify-center rounded-xl bg-[#42D1B9] hover:bg-[#2ABBA4] text-[#0D1B3E] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-400 dark:text-zinc-600 mt-1.5 px-1">
              Enter for at sende · Shift+Enter for ny linje
            </p>
          </div>
        </div>
      )}
    </>
  )
}

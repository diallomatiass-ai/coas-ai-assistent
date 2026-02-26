const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api';

async function fetchApi(path: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    fetchApi('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (data: { email: string; name: string; password: string; company_name?: string }) =>
    fetchApi('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () => fetchApi('/auth/me'),

  // Dashboard
  getDashboardSummary: () => fetchApi('/emails/dashboard/summary'),

  // Emails
  generateSuggestion: (id: string) => fetchApi(`/emails/${id}/generate-suggestion`, { method: 'POST' }),
  listEmails: (params?: { category?: string; urgency?: string; is_read?: boolean; search?: string; skip?: number; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) searchParams.set(k, String(v));
      });
    }
    const qs = searchParams.toString();
    return fetchApi(`/emails/${qs ? `?${qs}` : ''}`);
  },
  getEmail: (id: string) => fetchApi(`/emails/${id}`),
  getEmailStats: () => fetchApi('/emails/stats/summary'),
  getEmailThread: (id: string) => fetchApi(`/emails/${id}/thread`),
  getEmailCustomerHistory: (id: string) => fetchApi(`/emails/${id}/customer-history`),
  composeEmail: (data: { to_address: string; subject: string; body: string; account_id: string }) =>
    fetchApi('/emails/compose', { method: 'POST', body: JSON.stringify(data) }),
  generateComposeDraft: (data: { instructions: string; to_address?: string; subject?: string; tones?: string[] }) =>
    fetchApi('/emails/compose/ai-draft', { method: 'POST', body: JSON.stringify(data) }),
  listSentEmails: (params?: { skip?: number; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) searchParams.set(k, String(v));
      });
    }
    const qs = searchParams.toString();
    return fetchApi(`/emails/sent${qs ? `?${qs}` : ''}`);
  },

  // Reminders
  listReminders: () => fetchApi('/reminders/'),
  dismissReminder: (id: string) => fetchApi(`/reminders/${id}/dismiss`, { method: 'POST' }),
  getReminderCount: () => fetchApi('/reminders/count'),

  // Suggestions
  actionSuggestion: (id: string, action: string, editedText?: string) =>
    fetchApi(`/suggestions/${id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, edited_text: editedText }),
    }),
  sendSuggestion: (id: string) =>
    fetchApi(`/suggestions/${id}/send`, { method: 'POST' }),
  refineSuggestion: (id: string, prompt: string, currentText?: string) =>
    fetchApi(`/suggestions/${id}/refine`, {
      method: 'POST',
      body: JSON.stringify({ prompt, current_text: currentText }),
    }),

  // Templates
  listTemplates: () => fetchApi('/templates/'),
  createTemplate: (data: { name: string; category?: string; body: string }) =>
    fetchApi('/templates/', { method: 'POST', body: JSON.stringify(data) }),
  updateTemplate: (id: string, data: { name?: string; category?: string; body?: string }) =>
    fetchApi(`/templates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTemplate: (id: string) =>
    fetchApi(`/templates/${id}`, { method: 'DELETE' }),

  // Knowledge
  listKnowledge: (entryType?: string) =>
    fetchApi(`/knowledge/${entryType ? `?entry_type=${entryType}` : ''}`),
  createKnowledge: (data: { entry_type: string; title: string; content: string }) =>
    fetchApi('/knowledge/', { method: 'POST', body: JSON.stringify(data) }),
  updateKnowledge: (id: string, data: { entry_type?: string; title?: string; content?: string }) =>
    fetchApi(`/knowledge/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteKnowledge: (id: string) =>
    fetchApi(`/knowledge/${id}`, { method: 'DELETE' }),

  // Chat / AI Command
  sendCommand: (message: string, confirm?: boolean, pendingAction?: Record<string, unknown>) =>
    fetchApi('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, confirm: confirm ?? false, pending_action: pendingAction ?? null }),
    }),

  // AI Secretary
  getSecretary: () => fetchApi('/ai-secretary/'),
  createSecretary: (data: {
    business_name: string;
    industry: string;
    phone_number?: string;
    cvr_number?: string;
    contact_persons?: { name: string; phone: string; role: string; priority: number; notify_sms: boolean }[];
    business_address?: string;
    business_email?: string;
    voice_id?: string;
    greeting_text: string;
    system_prompt: string;
    required_fields: string[];
    knowledge_items: Record<string, string>;
    ivr_options?: { key: string; label: string; action: string; enabled: boolean }[];
  }) => fetchApi('/ai-secretary/', { method: 'POST', body: JSON.stringify(data) }),
  updateSecretary: (data: {
    business_name?: string;
    industry?: string;
    phone_number?: string;
    cvr_number?: string;
    contact_persons?: { name: string; phone: string; role: string; priority: number; notify_sms: boolean }[];
    business_address?: string;
    business_email?: string;
    voice_id?: string;
    greeting_text?: string;
    system_prompt?: string;
    required_fields?: string[];
    knowledge_items?: Record<string, string>;
    ivr_options?: { key: string; label: string; action: string; enabled: boolean }[];
    is_active?: boolean;
  }) => fetchApi('/ai-secretary/', { method: 'PUT', body: JSON.stringify(data) }),
  getIndustries: (businessName?: string) =>
    fetchApi(`/ai-secretary/industries${businessName ? `?business_name=${encodeURIComponent(businessName)}` : ''}`),
  getIndustryTemplate: (id: string, businessName?: string) =>
    fetchApi(`/ai-secretary/industries/${id}${businessName ? `?business_name=${encodeURIComponent(businessName)}` : ''}`),
  getCallDashboard: () => fetchApi('/ai-secretary/dashboard'),
  getCalls: () => fetchApi('/ai-secretary/calls'),
  updateCallStatus: (id: string, data: { status?: string; notes?: string }) =>
    fetchApi(`/ai-secretary/calls/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // AI Secretary — create call
  createCall: (data: {
    caller_name?: string;
    caller_phone?: string;
    caller_address?: string;
    summary: string;
    transcript?: string;
    required_fields_data?: Record<string, unknown>;
    urgency?: string;
    called_at?: string;
  }) => fetchApi('/ai-secretary/calls', { method: 'POST', body: JSON.stringify(data) }),

  // Customers
  listCustomers: (params?: { search?: string; status?: string; skip?: number; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) searchParams.set(k, String(v));
      });
    }
    const qs = searchParams.toString();
    return fetchApi(`/customers/${qs ? `?${qs}` : ''}`);
  },
  getCustomer: (id: string) => fetchApi(`/customers/${id}`),
  createCustomer: (data: {
    name: string;
    phone?: string;
    email?: string;
    address_street?: string;
    address_zip?: string;
    address_city?: string;
    source?: string;
    tags?: string[];
    estimated_value?: number;
    notes?: string;
  }) => fetchApi('/customers/', { method: 'POST', body: JSON.stringify(data) }),
  updateCustomer: (id: string, data: Record<string, unknown>) =>
    fetchApi(`/customers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCustomer: (id: string) =>
    fetchApi(`/customers/${id}`, { method: 'DELETE' }),
  getCustomerTimeline: (id: string) => fetchApi(`/customers/${id}/timeline`),
  mergeCustomers: (primaryId: string, secondaryId: string) =>
    fetchApi(`/customers/${primaryId}/merge/${secondaryId}`, { method: 'POST' }),
  getCustomerDashboard: () => fetchApi('/customers/dashboard'),
  pushToOrdrestyring: (customerId: string, data?: { description?: string }) =>
    fetchApi(`/customers/${customerId}/push-ordrestyring`, { method: 'POST', body: JSON.stringify(data || {}) }),
  getOrdrestyringStatus: () => fetchApi('/customers/ordrestyring-status'),

  // Action Items
  listActionItems: (params?: { status?: string; customer_id?: string; overdue?: boolean }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) searchParams.set(k, String(v));
      });
    }
    const qs = searchParams.toString();
    return fetchApi(`/action-items/${qs ? `?${qs}` : ''}`);
  },
  getActionItemsDashboard: () => fetchApi('/action-items/dashboard'),
  createActionItem: (data: {
    customer_id: string;
    action: string;
    description?: string;
    deadline?: string;
    source_type?: string;
  }) => fetchApi('/action-items/', { method: 'POST', body: JSON.stringify(data) }),
  updateActionItem: (id: string, data: Record<string, unknown>) =>
    fetchApi(`/action-items/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteActionItem: (id: string) =>
    fetchApi(`/action-items/${id}`, { method: 'DELETE' }),
  generateFollowupDraft: (id: string) =>
    fetchApi(`/action-items/${id}/generate-draft`, { method: 'POST' }),

  // Kalender
  getCalendarStatus: () => fetchApi('/calendar/status'),
  getCalendarEvents: (start?: string, end?: string) => {
    const params = new URLSearchParams()
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    const qs = params.toString()
    return fetchApi(`/calendar/events${qs ? `?${qs}` : ''}`)
  },
  createCalendarEvent: (data: {
    title: string;
    description?: string;
    start_time: string;
    end_time: string;
    action_item_id?: string;
    call_id?: string;
    event_type?: string;
  }) => fetchApi('/calendar/events', { method: 'POST', body: JSON.stringify(data) }),
  updateCalendarEvent: (id: string, data: {
    title?: string;
    description?: string;
    start_time?: string;
    end_time?: string;
  }) => fetchApi(`/calendar/events/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCalendarEvent: (id: string) =>
    fetchApi(`/calendar/events/${id}`, { method: 'DELETE' }),

  // Accounts
  listAccounts: () => fetchApi('/webhooks/accounts'),
  connectGmail: () => fetchApi('/webhooks/gmail/connect'),
  connectOutlook: () => fetchApi('/webhooks/outlook/connect'),
  disconnectAccount: (id: string) =>
    fetchApi(`/webhooks/accounts/${id}`, { method: 'DELETE' }),
};

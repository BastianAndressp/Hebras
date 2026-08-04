"use client";

import { FormEvent, useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";

import Header from "./components/Header";
import TabNavigation from "./components/TabNavigation";
import ResumenTab from "./components/ResumenTab";
import InboxTab from "./components/InboxTab";
import BotConfigTab from "./components/BotConfigTab";
import PromptEditorTab from "./components/PromptEditorTab";
import KnowledgeTab from "./components/KnowledgeTab";
import StatsTab from "./components/StatsTab";
import TeamTab from "./components/TeamTab";
import BillingTab from "./components/BillingTab";
import WhatsAppTab from "./components/WhatsAppTab";
import ApiKeysTab from "./components/ApiKeysTab";
import HoursTab from "./components/HoursTab";
import HandoffTab from "./components/HandoffTab";
import LogsTab from "./components/LogsTab";
import NotificationsTab from "./components/NotificationsTab";
import ProfileTab from "./components/ProfileTab";

const API = process.env.NEXT_PUBLIC_API_URL || "/api";

type Bot = {
  id?: string;
  name: string;
  phone_number_id: string;
  system_prompt: string;
  model: string;
  fallback_model?: string;
  temperature: number;
  max_tokens: number;
  status: string;
  company_id?: string;
};

type Rule = {
  keywords: string[];
  max_bot_attempts: number;
  notification_email?: string;
  ai_handoff_phrase?: string | null;
};

type DocumentRow = {
  id: string;
  title: string;
  status: string;
  chunk_count: number;
  created_at: string;
};

type Plan = {
  id: string;
  slug: string;
  name: string;
  monthly_message_limit: number;
  price_amount: number;
  currency: string;
  is_active: boolean;
};

type Billing = {
  subscription: null | {
    id: string;
    status: string;
    trial_ends_at: string | null;
    days_remaining: number | null;
    current_period_start: string;
    current_period_end: string;
    plan: Plan;
  };
  plans: Plan[];
  monthly_message_limit: number;
  messages_used: number;
  estimated_cost_usd: number;
  total_conversations: number;
};

type AuditLogRow = {
  id: string;
  actor_id: string | null;
  action: string;
  created_at: string;
};

type TeamMember = {
  id: string;
  user_id: string;
  role: string;
  created_at: string;
};

type SettingsData = {
  business_hours_enabled: boolean;
  business_hours: any;
  out_of_hours_message: string;
  monthly_spending_limit_usd: number;
  default_language: string;
};

type ApiKeysState = {
  has_whatsapp_access_token: boolean;
  has_whatsapp_app_secret: boolean;
  has_openrouter_api_key: boolean;
};

type NotificationItem = {
  id: string;
  title: string;
  message: string;
  severity: string;
  is_read: boolean;
  created_at: string;
};

async function api(path: string, token: string, options: RequestInit = {}) {
  const response = await fetch(`${API}/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const errData = await response.json().catch(() => ({ detail: "Error de API" }));
    let msg = "Error de API";
    if (typeof errData.detail === "string") {
      msg = errData.detail;
    } else if (Array.isArray(errData.detail)) {
      msg = errData.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
    } else if (errData.detail && typeof errData.detail === "object") {
      msg = JSON.stringify(errData.detail);
    }
    throw new Error(msg);
  }
  return response.json();
}

export default function Dashboard() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [bot, setBot] = useState<Bot | null>(null);
  const [bots, setBots] = useState<Bot[]>([]);
  const [selectedBotId, setSelectedBotId] = useState("");
  const [rule, setRule] = useState<Rule | null>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [conversations, setConversations] = useState<any[]>([]);
  const [convFilter, setConvFilter] = useState("all");
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [billing, setBilling] = useState<Billing | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [auditLogs, setAuditLogs] = useState<AuditLogRow[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [newMemberId, setNewMemberId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("staff");
  const [settingsData, setSettingsData] = useState<SettingsData>({
    business_hours_enabled: false,
    business_hours: {
      timezone: "America/Santiago",
      schedule: {
        mon: { start: "09:00", end: "18:00", active: true },
        tue: { start: "09:00", end: "18:00", active: true },
        wed: { start: "09:00", end: "18:00", active: true },
        thu: { start: "09:00", end: "18:00", active: true },
        fri: { start: "09:00", end: "18:00", active: true },
        sat: { start: "10:00", end: "14:00", active: false },
        sun: { start: "10:00", end: "14:00", active: false },
      },
    },
    out_of_hours_message:
      "Gracias por escribirnos. Nuestro horario de atención es de Lunes a Viernes de 09:00 a 18:00 hrs. Te responderemos en cuanto abramos.",
    monthly_spending_limit_usd: 100,
    default_language: "es",
  });
  const [apiKeysState, setApiKeysState] = useState<ApiKeysState>({
    has_whatsapp_access_token: false,
    has_whatsapp_app_secret: false,
    has_openrouter_api_key: false,
  });
  const [newWaToken, setNewWaToken] = useState("");
  const [newWaSecret, setNewWaSecret] = useState("");
  const [newOrKey, setNewOrKey] = useState("");
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [webhookInfo, setWebhookInfo] = useState<{ webhook_url: string; verify_token: string } | null>(null);

  const [tab, setTab] = useState("resumen");
  const [error, setError] = useState("");
  const [bootstrapping, setBootstrapping] = useState(true);

  const [authMode, setAuthMode] = useState<"login" | "signup" | "verify" | "forgot" | "reset">("login");
  const [companyName, setCompanyName] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [notice, setNotice] = useState("");

  const load = async (jwt = token, botId?: string) => {
    try {
      setError("");
      const botsList: Bot[] = await api("/bots", jwt);
      setBots(botsList);
      const activeBotId = botId || botsList[0]?.id || "";
      setSelectedBotId(activeBotId);
      const botQuery = activeBotId ? `?bot_id=${activeBotId}` : "";
      const [b, r, m, c, d, bl, a, t, st, ak, n, wh] = await Promise.all([
        api(`/bot${botQuery}`, jwt),
        api(`/handoff-rule${botQuery}`, jwt),
        api("/metrics", jwt),
        api("/conversations", jwt),
        api(`/knowledge/documents${botQuery}`, jwt),
        api("/billing", jwt),
        api("/audit-logs", jwt),
        api("/team/members", jwt),
        api(`/settings${botQuery}`, jwt).catch(() => null),
        api("/api-keys", jwt).catch(() => null),
        api("/notifications", jwt).catch(() => []),
        api("/webhook-info", jwt).catch(() => null),
      ]);
      setBot(b);
      setRule(r);
      setMetrics(m);
      setConversations(c);
      setDocuments(d);
      setBilling(bl);
      setAuditLogs(a);
      setTeamMembers(t);
      if (st) setSettingsData(st);
      if (ak) setApiKeysState(ak);
      setNotifications(n);
      if (wh) {
        // API es NEXT_PUBLIC_API_URL (horneada en el build, ver docker-compose.yml). El
        // webhook de Meta le habla directo a la API, nunca a través del proxy /api del
        // dashboard (next.config.js solo reescribe /api/*, no /webhooks/*).
        const isAbsoluteApiUrl = API.startsWith("http://") || API.startsWith("https://");
        setWebhookInfo({
          webhook_url: isAbsoluteApiUrl
            ? `${API}${wh.webhook_path}`
            : `<URL_PUBLICA_DE_TU_API>${wh.webhook_path}`,
          verify_token: wh.verify_token,
        });
      }
      setSelectedPlanId(bl.subscription?.plan.id || bl.plans[0]?.id || "");
    } catch (e: any) {
      setBot(null);
      localStorage.removeItem("whatsapp-ai-token");
      setToken("");
      throw e;
    }
  };

  const switchBot = async (botId: string) => {
    setSelectedBotId(botId);
    try {
      setError("");
      const botQuery = `?bot_id=${botId}`;
      const [b, r, d, st] = await Promise.all([
        api(`/bot${botQuery}`, token),
        api(`/handoff-rule${botQuery}`, token),
        api(`/knowledge/documents${botQuery}`, token),
        api(`/settings${botQuery}`, token).catch(() => null),
      ]);
      setBot(b);
      setRule(r);
      setDocuments(d);
      if (st) setSettingsData(st);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const createBot = async (data: { name: string; phone_number_id: string }) => {
    try {
      setError("");
      const created = await api("/bots", token, { method: "POST", body: JSON.stringify(data) });
      setBots((prev) => [...prev, created]);
      await switchBot(created.id);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const deleteBot = async (botId: string) => {
    try {
      setError("");
      await api(`/bots/${botId}`, token, { method: "DELETE" });
      const remaining = bots.filter((b) => b.id !== botId);
      setBots(remaining);
      if (selectedBotId === botId && remaining[0]?.id) {
        await switchBot(remaining[0].id);
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  // "Despierta" la API apenas se carga el dashboard, incluso antes de saber si hay
  // sesión guardada -- en un plan gratuito de Render, el servicio se duerme tras ~15
  // min sin tráfico y la primera request tarda en responder o falla. Disparar esto en
  // paralelo (sin esperarlo) le da tiempo a levantar mientras el usuario todavía está
  // mirando la pantalla de login.
  useEffect(() => {
    fetch(`${API}/health`).catch(() => {});
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem("whatsapp-ai-token");
    if (saved) {
      setToken(saved);
      load(saved)
        .catch(() => {
          setError("Sesión no autorizada. Por favor inicia sesión.");
        })
        .finally(() => setBootstrapping(false));
      return;
    }
    setBootstrapping(false);
  }, []);

  // Mientras el Inbox está abierto, refresca las conversaciones cada pocos segundos —
  // los mensajes de WhatsApp llegan de forma asíncrona (webhook -> worker -> DB), así que
  // sin esto el usuario solo los veía al refrescar la página a mano.
  useEffect(() => {
    if (tab !== "inbox" || !token) return;
    const interval = setInterval(() => {
      api("/conversations", token).then(setConversations).catch(() => {});
    }, 4000);
    return () => clearInterval(interval);
  }, [tab, token]);

  const parseResponseJson = async (res: Response) => {
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      const text = await res.text().catch(() => "");
      throw new Error(text.substring(0, 150) || `Error HTTP ${res.status} del servidor`);
    }
    return res.json();
  };

  const handleSignUp = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const res = await fetch(`${API}/v1/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, company_name: companyName || "Mi Empresa" }),
      });
      const data = await parseResponseJson(res);
      if (!res.ok) {
        let msg = typeof data.detail === "string" ? data.detail : "Error al registrar cuenta";
        if (Array.isArray(data.detail)) msg = data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
        throw new Error(msg);
      }
      setAuthMode("verify");
      setNotice(data.message);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleVerifyCode = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const res = await fetch(`${API}/v1/auth/verify-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code: verificationCode }),
      });
      const data = await parseResponseJson(res);
      if (!res.ok) {
        let msg = typeof data.detail === "string" ? data.detail : "Código incorrecto";
        if (Array.isArray(data.detail)) msg = data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
        throw new Error(msg);
      }
      setToken(data.access_token);
      localStorage.setItem("whatsapp-ai-token", data.access_token);
      await load(data.access_token);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleResendCode = async () => {
    setError("");
    setNotice("");
    try {
      const res = await fetch(`${API}/v1/auth/resend-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await parseResponseJson(res);
      if (!res.ok) {
        let msg = typeof data.detail === "string" ? data.detail : "Error al reenviar código";
        throw new Error(msg);
      }
      setNotice(data.message);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleForgotPassword = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const res = await fetch(`${API}/v1/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await parseResponseJson(res);
      if (!res.ok) {
        let msg = typeof data.detail === "string" ? data.detail : "No se pudo enviar el código";
        throw new Error(msg);
      }
      setAuthMode("reset");
      setNotice(data.message);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleResetPassword = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const res = await fetch(`${API}/v1/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code: resetCode, new_password: newPassword }),
      });
      const data = await parseResponseJson(res);
      if (!res.ok) {
        let msg = typeof data.detail === "string" ? data.detail : "No se pudo restablecer la contraseña";
        throw new Error(msg);
      }
      setToken(data.access_token);
      localStorage.setItem("whatsapp-ai-token", data.access_token);
      setResetCode("");
      setNewPassword("");
      await load(data.access_token);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const login = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
      if (url && key) {
        const { data, error: authError } = await createClient(url, key).auth.signInWithPassword({ email, password });
        if (authError || !data.session) throw new Error(authError?.message || "No se creó una sesión");
        setToken(data.session.access_token);
        localStorage.setItem("whatsapp-ai-token", data.session.access_token);
        await load(data.session.access_token);
      } else {
        const res = await fetch(`${API}/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await parseResponseJson(res);
        if (!res.ok) {
          if (data.detail && typeof data.detail === "object" && data.detail.requires_verification) {
            setAuthMode("verify");
            setNotice(data.detail.message || "Debes verificar tu correo.");
            return;
          }
          let msg = typeof data.detail === "string" ? data.detail : "Error al ingresar";
          if (Array.isArray(data.detail)) msg = data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
          throw new Error(msg);
        }
        setToken(data.access_token);
        localStorage.setItem("whatsapp-ai-token", data.access_token);
        await load(data.access_token);
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  const saveBot = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const updated = await api(`/bot?bot_id=${selectedBotId}`, token, { method: "PUT", body: JSON.stringify(bot) });
      setBot(updated);
      setBots((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
    } catch (e: any) {
      setError(e.message);
    }
  };

  const saveRule = async (e: FormEvent) => {
    e.preventDefault();
    try {
      setRule(
        await api(`/handoff-rule?bot_id=${selectedBotId}`, token, {
          method: "PUT",
          body: JSON.stringify(rule),
        })
      );
    } catch (e: any) {
      setError(e.message);
    }
  };

  const saveSettings = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const updated = await api(`/settings?bot_id=${selectedBotId}`, token, {
        method: "PUT",
        body: JSON.stringify(settingsData),
      });
      setSettingsData(updated);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const saveApiKeys = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const updated = await api("/api-keys", token, {
        method: "PUT",
        body: JSON.stringify({
          whatsapp_access_token: newWaToken || undefined,
          whatsapp_app_secret: newWaSecret || undefined,
          openrouter_api_key: newOrKey || undefined,
        }),
      });
      setApiKeysState(updated);
      setNewWaToken("");
      setNewWaSecret("");
      setNewOrKey("");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const saveBilling = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      // Sin pasarela de pago todavía: esto no activa el plan al instante, solo registra
      // la solicitud (ver POST /v1/billing/request-upgrade en el backend).
      const res = await api("/billing/request-upgrade", token, {
        method: "POST",
        body: JSON.stringify({ plan_id: selectedPlanId }),
      });
      setNotice(res.message || "Solicitud enviada. Te contactaremos para activar el plan.");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const addMember = async (e: FormEvent) => {
    e.preventDefault();
    const uuidRegex = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
    if (!newMemberId || !uuidRegex.test(newMemberId.trim())) {
      setError("Por favor ingresa un UUID válido para el usuario (ej: 44444444-4444-4444-4444-444444444444)");
      return;
    }
    try {
      await api("/team/members", token, {
        method: "POST",
        body: JSON.stringify({ user_id: newMemberId.trim(), role: newMemberRole }),
      });
      setNewMemberId("");
      setNewMemberRole("staff");
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const updateMemberRole = async (userId: string, role: string) => {
    try {
      await api(`/team/members/${userId}`, token, {
        method: "PUT",
        body: JSON.stringify({ role }),
      });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const removeMember = async (userId: string) => {
    try {
      await api(`/team/members/${userId}`, token, {
        method: "DELETE",
      });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const saveDocument = async (e: FormEvent) => {
    e.preventDefault();
    try {
      let created: any;
      if (documentFile) {
        const formData = new FormData();
        formData.append("title", documentTitle);
        formData.append("file", documentFile);
        const response = await fetch(`${API}/v1/knowledge/documents/upload?bot_id=${selectedBotId}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        if (!response.ok) {
          const errData = await response.json().catch(() => ({ detail: "Error" }));
          let msg = typeof errData.detail === "string" ? errData.detail : "Error al subir documento";
          throw new Error(msg);
        }
        created = await response.json();
      } else {
        created = await api(`/knowledge/documents?bot_id=${selectedBotId}`, token, {
          method: "POST",
          body: JSON.stringify({
            title: documentTitle,
            content: documentContent,
          }),
        });
      }
      setDocuments([{ ...created, created_at: created.created_at }, ...documents]);
      setDocumentTitle("");
      setDocumentContent("");
      setDocumentFile(null);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleToggleStatus = async (conversationId: string, newStatus: string) => {
    try {
      await api(`/conversations/${conversationId}/status`, token, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleSendMessage = async (conversationId: string, content: string) => {
    try {
      await api(`/conversations/${conversationId}/messages`, token, {
        method: "POST",
        body: JSON.stringify({ content }),
      });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("whatsapp-ai-token");
    setToken("");
    setBot(null);
  };

  if (bootstrapping)
    return (
      <main>
        <header>
          <div className="brand-title">
            <div className="brand-logo">H</div>
            <h1>Hebras</h1>
          </div>
        </header>
        <div className="card">
          <h2>Cargando Dashboard...</h2>
          <p className="muted">Inicializando tenant y cargando configuración.</p>
        </div>
      </main>
    );

  if (!bot)
    return (
      <main>
        <header>
          <div className="brand-title">
            <div className="brand-logo">H</div>
            <h1>Hebras</h1>
          </div>
        </header>
        <div className="card" style={{ maxWidth: 460, margin: "40px auto" }}>
          {authMode === "login" && (
            <div>
              <h2>Ingresar a tu Cuenta</h2>
              <form onSubmit={login}>
                <label>Correo Electrónico</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@empresa.com"
                  required
                />
                <label>Contraseña</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
                <button style={{ marginTop: 20, width: "100%" }}>Iniciar Sesión</button>
              </form>
              <div style={{ marginTop: 12, textAlign: "center" }}>
                <button
                  type="button"
                  className="secondary"
                  style={{ padding: "4px 10px", fontSize: "12px" }}
                  onClick={() => {
                    setError("");
                    setNotice("");
                    setAuthMode("forgot");
                  }}
                >
                  ¿Olvidaste tu contraseña?
                </button>
              </div>
              <div style={{ marginTop: 16, textAlign: "center" }}>
                <span className="muted">¿No tienes cuenta? </span>
                <button
                  type="button"
                  className="secondary"
                  style={{ padding: "4px 10px", fontSize: "12px" }}
                  onClick={() => {
                    setError("");
                    setNotice("");
                    setAuthMode("signup");
                  }}
                >
                  Regístrate aquí
                </button>
              </div>
            </div>
          )}

          {authMode === "signup" && (
            <div>
              <h2>Crear Nueva Cuenta SaaS</h2>
              <form onSubmit={handleSignUp}>
                <label>Nombre de tu Empresa</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Ej: Clínica Dental DentalPro"
                  required
                />
                <label>Correo Electrónico</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="contacto@empresa.com"
                  required
                />
                <label>Contraseña</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mínimo 6 caracteres"
                  minLength={6}
                  required
                />
                <button style={{ marginTop: 20, width: "100%" }}>
                  Registrarme & Recibir Código
                </button>
              </form>
              <div style={{ marginTop: 16, textAlign: "center" }}>
                <span className="muted">¿Ya estás registrado? </span>
                <button
                  type="button"
                  className="secondary"
                  style={{ padding: "4px 10px", fontSize: "12px" }}
                  onClick={() => {
                    setError("");
                    setNotice("");
                    setAuthMode("login");
                  }}
                >
                  Iniciar Sesión
                </button>
              </div>
            </div>
          )}

          {authMode === "verify" && (
            <div>
              <h2>Validar Correo Electrónico</h2>
              <p className="muted">
                Ingresa el código de 6 dígitos que enviamos a <b>{email}</b>.
              </p>
              <form onSubmit={handleVerifyCode}>
                <label>Código de Verificación (6 dígitos)</label>
                <input
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  placeholder="123456"
                  maxLength={6}
                  required
                  style={{ fontSize: "20px", letterSpacing: "4px", textAlign: "center" }}
                />
                <button style={{ marginTop: 20, width: "100%" }}>
                  Validar
                </button>
              </form>
              <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", gap: 8 }}>
                <button
                  type="button"
                  className="secondary"
                  style={{ fontSize: "12px", width: "50%" }}
                  onClick={handleResendCode}
                >
                  Reenviar Código
                </button>
                <button
                  type="button"
                  className="secondary"
                  style={{ fontSize: "12px", width: "50%" }}
                  onClick={() => {
                    setError("");
                    setNotice("");
                    setAuthMode("login");
                  }}
                >
                  Volver al Login
                </button>
              </div>
            </div>
          )}

          {authMode === "forgot" && (
            <div>
              <h2>Recuperar Contraseña</h2>
              <p className="muted">
                Ingresa tu correo y te enviaremos un código para restablecer tu contraseña.
              </p>
              <form onSubmit={handleForgotPassword}>
                <label>Correo Electrónico</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@empresa.com"
                  required
                />
                <button style={{ marginTop: 20, width: "100%" }}>Enviar Código</button>
              </form>
              <div style={{ marginTop: 16, textAlign: "center" }}>
                <button
                  type="button"
                  className="secondary"
                  style={{ fontSize: "12px" }}
                  onClick={() => {
                    setError("");
                    setNotice("");
                    setAuthMode("login");
                  }}
                >
                  Volver al Login
                </button>
              </div>
            </div>
          )}

          {authMode === "reset" && (
            <div>
              <h2>Restablecer Contraseña</h2>
              <p className="muted">
                Ingresa el código de 6 dígitos que enviamos a <b>{email}</b> y tu nueva contraseña.
              </p>
              <form onSubmit={handleResetPassword}>
                <label>Código (6 dígitos)</label>
                <input
                  type="text"
                  value={resetCode}
                  onChange={(e) => setResetCode(e.target.value)}
                  placeholder="123456"
                  maxLength={6}
                  required
                  style={{ fontSize: "20px", letterSpacing: "4px", textAlign: "center" }}
                />
                <label>Nueva Contraseña</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Mínimo 6 caracteres"
                  minLength={6}
                  required
                />
                <button style={{ marginTop: 20, width: "100%" }}>Restablecer Contraseña</button>
              </form>
              <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", gap: 8 }}>
                <button
                  type="button"
                  className="secondary"
                  style={{ fontSize: "12px", width: "50%" }}
                  onClick={handleForgotPassword}
                >
                  Reenviar Código
                </button>
                <button
                  type="button"
                  className="secondary"
                  style={{ fontSize: "12px", width: "50%" }}
                  onClick={() => {
                    setError("");
                    setNotice("");
                    setAuthMode("login");
                  }}
                >
                  Volver al Login
                </button>
              </div>
            </div>
          )}

          {notice && (
            <div
              style={{
                marginTop: 16,
                padding: "10px 14px",
                background: "rgba(16, 185, 129, 0.15)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                color: "#34d399",
                borderRadius: "8px",
                fontSize: "13px",
              }}
            >
              {notice}
            </div>
          )}

          {error && <p className="error" style={{ marginTop: 16 }}>{error}</p>}
        </div>
      </main>
    );

  return (
    <main>
      <Header
        phone_number_id={bot.phone_number_id}
        status={bot.status}
        onLogout={handleLogout}
        bots={bots}
        selectedBotId={selectedBotId}
        onSelectBot={switchBot}
      />

      <TabNavigation activeTab={tab} onSelectTab={setTab} />

      {error && <div className="error">{error}</div>}
      {notice && (
        <div
          style={{
            marginBottom: 20,
            padding: "12px 16px",
            background: "rgba(16, 185, 129, 0.1)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#34d399",
            borderRadius: "10px",
            fontSize: "14px",
          }}
        >
          {notice}
        </div>
      )}

      {tab === "resumen" && (
        <ResumenTab
          metrics={metrics}
          bot={bot}
          documentCount={documents.length}
          businessHoursEnabled={settingsData.business_hours_enabled}
          isWhatsAppConnected={apiKeysState.has_whatsapp_access_token}
          subscription={billing?.subscription ?? null}
          onGoToBilling={() => setTab("facturacion")}
        />
      )}

      {tab === "inbox" && (
        <InboxTab
          conversations={conversations}
          convFilter={convFilter}
          setConvFilter={setConvFilter}
          onToggleStatus={handleToggleStatus}
          onSendMessage={handleSendMessage}
        />
      )}

      {tab === "bot" && (
        <BotConfigTab
          bot={bot}
          setBot={setBot}
          onSave={saveBot}
          bots={bots}
          onCreateBot={createBot}
          onDeleteBot={deleteBot}
        />
      )}

      {tab === "prompt" && (
        <PromptEditorTab bot={bot} setBot={setBot} onSave={saveBot} />
      )}

      {tab === "conocimiento" && (
        <KnowledgeTab
          documents={documents}
          documentTitle={documentTitle}
          setDocumentTitle={setDocumentTitle}
          documentContent={documentContent}
          setDocumentContent={setDocumentContent}
          documentFile={documentFile}
          setDocumentFile={setDocumentFile}
          onSave={saveDocument}
        />
      )}

      {tab === "estadisticas" && (
        <StatsTab
          messagesUsed={billing?.messages_used ?? 0}
          resolutionRate={metrics?.resolution_rate ?? 0}
        />
      )}

      {tab === "equipo" && (
        <TeamTab
          teamMembers={teamMembers}
          newMemberId={newMemberId}
          setNewMemberId={setNewMemberId}
          newMemberRole={newMemberRole}
          setNewMemberRole={setNewMemberRole}
          onAddMember={addMember}
          onUpdateRole={updateMemberRole}
          onRemoveMember={removeMember}
        />
      )}

      {tab === "facturacion" && billing && (
        <BillingTab
          billing={billing}
          selectedPlanId={selectedPlanId}
          setSelectedPlanId={setSelectedPlanId}
          onSave={saveBilling}
        />
      )}

      {tab === "whatsapp" && (
        <WhatsAppTab bot={bot} setBot={setBot} onSave={saveBot} webhookInfo={webhookInfo} />
      )}

      {tab === "apikeys" && (
        <ApiKeysTab
          apiKeysState={apiKeysState}
          newWaToken={newWaToken}
          setNewWaToken={setNewWaToken}
          newWaSecret={newWaSecret}
          setNewWaSecret={setNewWaSecret}
          newOrKey={newOrKey}
          setNewOrKey={setNewOrKey}
          onSave={saveApiKeys}
        />
      )}

      {tab === "horarios" && (
        <HoursTab
          settingsData={settingsData}
          setSettingsData={setSettingsData}
          onSave={saveSettings}
        />
      )}

      {tab === "derivacion" && rule && (
        <HandoffTab key={selectedBotId} rule={rule} setRule={setRule} onSave={saveRule} />
      )}

      {tab === "logs" && <LogsTab auditLogs={auditLogs} />}

      {tab === "notificaciones" && (
        <NotificationsTab notifications={notifications} />
      )}

      {tab === "perfil" && (
        <ProfileTab
          companyId={bot?.company_id || ""}
          settingsData={settingsData}
          setSettingsData={setSettingsData}
          onSave={saveSettings}
        />
      )}
    </main>
  );
}

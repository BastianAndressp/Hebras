"use client";

import { FormEvent } from "react";

type Plan = {
  id: string;
  slug: string;
  name: string;
  monthly_message_limit: number;
  price_amount: number;
  currency: string;
  is_active: boolean;
};

function formatPrice(amount: number, currency: string): string {
  if (currency === "CLP") {
    return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(amount);
  }
  return `${currency} ${amount}`;
}

function statusInfo(status: string): { label: string; className: string } {
  switch (status) {
    case "trialing":
      return { label: "Prueba gratuita activa", className: "badge-handoff" };
    case "active":
      return { label: "Activo", className: "badge-active" };
    case "trial_expired":
      return { label: "Prueba vencida", className: "badge-error" };
    case "canceled":
      return { label: "Cancelado", className: "badge-error" };
    case "no_subscription":
      return { label: "Sin suscripción", className: "badge-error" };
    default:
      return { label: status, className: "badge-closed" };
  }
}

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

type BillingTabProps = {
  billing: Billing;
  selectedPlanId: string;
  setSelectedPlanId: (planId: string) => void;
  onSave: (e: FormEvent) => void;
};

export default function BillingTab({
  billing,
  selectedPlanId,
  setSelectedPlanId,
  onSave,
}: BillingTabProps) {
  const subscription = billing.subscription;
  const status = subscription?.status || "no_subscription";
  const { label, className } = statusInfo(status);
  const usagePct = billing.monthly_message_limit > 0
    ? Math.min(100, Math.round((billing.messages_used / billing.monthly_message_limit) * 100))
    : 0;
  const usageColor = usagePct >= 100 ? "#f87171" : usagePct >= 80 ? "#fbbf24" : "#34d399";

  return (
    <>
      {status === "trialing" && subscription?.days_remaining !== null && subscription?.days_remaining !== undefined && (
        <div
          className="card"
          style={{
            marginBottom: 16,
            borderColor: "rgba(245, 158, 11, 0.35)",
            background: "rgba(245, 158, 11, 0.08)",
          }}
        >
          <b>Estás en tu prueba gratuita.</b>{" "}
          {subscription.days_remaining > 0
            ? `Te quedan ${subscription.days_remaining} día${subscription.days_remaining === 1 ? "" : "s"}.`
            : "Termina hoy."}{" "}
          Cuando se acabe, el bot dejará de responder hasta que actives un plan pagado — tus datos y configuración quedan intactos.
        </div>
      )}

      {(status === "trial_expired" || status === "no_subscription" || status === "canceled") && (
        <div className="error" style={{ marginBottom: 16 }}>
          <b>El bot no está respondiendo.</b>{" "}
          {status === "trial_expired"
            ? "Tu período de prueba terminó."
            : status === "canceled"
            ? "Tu suscripción fue cancelada."
            : "No tienes una suscripción activa."}{" "}
          Solicita un plan más abajo y te contactaremos para activarlo.
        </div>
      )}

      <form className="card" onSubmit={onSave}>
        <h2>Suscripción & Facturación SaaS</h2>
        <div className="conversation-box">
          <b>Plan Actual:</b> {subscription?.plan.name || "Sin Plan"} ·
          <span style={{ marginLeft: 8 }} className={`badge ${className}`}>
            {label}
          </span>
          <div style={{ marginTop: 12 }} className="muted">
            Consumo de mensajes: <b>{billing.messages_used}</b> / {billing.monthly_message_limit} este mes.
          </div>
          <div
            style={{
              marginTop: 6,
              height: 8,
              borderRadius: 999,
              background: "rgba(255,255,255,0.08)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${usagePct}%`,
                height: "100%",
                background: usageColor,
                transition: "width 0.3s ease",
              }}
            />
          </div>
          {usagePct >= 80 && (
            <div className="muted" style={{ marginTop: 6, color: usageColor }}>
              {usagePct >= 100
                ? "Alcanzaste el límite de mensajes de este mes."
                : "Te estás acercando al límite de mensajes de este mes."}
            </div>
          )}
          <div className="muted" style={{ marginTop: 8 }}>
            Costo acumulado de consumo IA: <b>${billing.estimated_cost_usd} USD</b>.
          </div>
        </div>

        <label style={{ marginTop: 20 }}>Solicitar Plan</label>
        <select
          value={selectedPlanId}
          onChange={(e) => setSelectedPlanId(e.target.value)}
        >
          {billing.plans.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} — {formatPrice(p.price_amount, p.currency)}/mes ({p.monthly_message_limit} msgs)
            </option>
          ))}
        </select>
        <p className="muted" style={{ marginTop: 8 }}>
          Sin pasarela de pago automática todavía: al solicitar un plan te contactaremos para coordinar el pago y activarlo.
        </p>
        <button style={{ marginTop: 12 }}>Solicitar Cambio de Plan</button>
      </form>
    </>
  );
}

"use client";

type Subscription = {
  status: string;
  days_remaining: number | null;
  plan: { name: string };
} | null;

type ResumenTabProps = {
  metrics: {
    conversations: number;
    handoffs: number;
    resolution_rate: number;
    estimated_cost_usd: number;
  } | null;
  bot: {
    model: string;
    phone_number_id: string;
  };
  documentCount: number;
  businessHoursEnabled: boolean;
  isWhatsAppConnected?: boolean;
  subscription?: Subscription;
  onGoToBilling?: () => void;
};

export default function ResumenTab({
  metrics,
  bot,
  documentCount,
  businessHoursEnabled,
  isWhatsAppConnected = false,
  subscription = null,
  onGoToBilling,
}: ResumenTabProps) {
  const status = subscription?.status;

  return (
    <>
      {status === "trialing" && subscription?.days_remaining !== null && subscription?.days_remaining !== undefined && (
        <div
          className="card"
          style={{
            marginBottom: 20,
            borderColor: "rgba(245, 158, 11, 0.35)",
            background: "rgba(245, 158, 11, 0.08)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <span>
            <b>Prueba gratuita de {subscription.plan.name}:</b>{" "}
            {subscription.days_remaining > 0
              ? `te quedan ${subscription.days_remaining} día${subscription.days_remaining === 1 ? "" : "s"}.`
              : "termina hoy."}
          </span>
          {onGoToBilling && (
            <button type="button" className="secondary" onClick={onGoToBilling}>
              Ver planes
            </button>
          )}
        </div>
      )}

      {(status === "trial_expired" || status === "no_subscription" || status === "canceled") && (
        <div
          className="error"
          style={{ marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}
        >
          <span>
            <b>El bot no está respondiendo.</b>{" "}
            {status === "trial_expired" ? "Tu prueba gratuita terminó." : "No tienes un plan activo."} Activa un plan para reanudarlo.
          </span>
          {onGoToBilling && (
            <button type="button" onClick={onGoToBilling}>
              Activar plan
            </button>
          )}
        </div>
      )}

      <div className="grid">
        <div className="card metric-card">
          <span className="metric-title">Conversaciones Totales</span>
          <div className="metric">{metrics?.conversations ?? 0}</div>
        </div>
        <div className="card metric-card">
          <span className="metric-title">Derivadas a Humano</span>
          <div className="metric">{metrics?.handoffs ?? 0}</div>
        </div>
        <div className="card metric-card">
          <span className="metric-title">Resolución Sin Humano</span>
          <div className="metric">{metrics?.resolution_rate ?? 0}%</div>
        </div>
        <div className="card metric-card">
          <span className="metric-title">Costo Est. IA (USD)</span>
          <div className="metric">${metrics?.estimated_cost_usd ?? 0}</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <h2>Estado Operativo del Tenant</h2>
        <div className="form-grid" style={{ marginTop: 16 }}>
          <div className="conversation-box">
            <b>Conexión WhatsApp API:</b>{" "}
            {isWhatsAppConnected ? (
              <span className="badge badge-active">Verificada (Cloud API)</span>
            ) : (
              <span className="badge badge-error">Sin Configurar / Pendiente</span>
            )}
          </div>
          <div className="conversation-box">
            <b>Motor de IA:</b> <span>{bot.model}</span>
          </div>
          <div className="conversation-box">
            <b>Base RAG Vectorial:</b>{" "}
            <span>{documentCount} documentos indexados</span>
          </div>
          <div className="conversation-box">
            <b>Horario de Atención:</b>{" "}
            <span>
              {businessHoursEnabled ? "Activo (Controlado)" : "24/7 Libre"}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

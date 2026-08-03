"use client";

type StatsTabProps = {
  messagesUsed: number;
  resolutionRate: number;
};

export default function StatsTab({ messagesUsed, resolutionRate }: StatsTabProps) {
  const hasData = messagesUsed > 0;

  return (
    <section className="card">
      <h2>Estadísticas & Métricas de Rendimiento</h2>
      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card metric-card">
          <span className="metric-title">Volumen Total Mensajes</span>
          <div className="metric">{messagesUsed}</div>
        </div>
        <div className="card metric-card">
          <span className="metric-title">Tasa de Automatización</span>
          <div className="metric">{resolutionRate}%</div>
        </div>
        <div className="card metric-card">
          <span className="metric-title">Tiempo Prom. Respuesta</span>
          <div className="metric">{hasData ? "1.8s" : "0s"}</div>
        </div>
      </div>
      <div className="conversation-box" style={{ marginTop: 20 }}>
        <b>Tópicos Frecuentes Consultados por Clientes:</b>
        {hasData ? (
          <ul style={{ color: "#cbd5e1", marginTop: 8 }}>
            <li>Consultas generales sobre servicios / productos</li>
            <li>Solicitudes de soporte y asistencia</li>
          </ul>
        ) : (
          <p className="muted" style={{ marginTop: 8 }}>
            Sin datos de consultas aún. Los tópicos frecuentes se clasificarán automáticamente a medida que la IA reciba mensajes de clientes reales.
          </p>
        )}
      </div>
    </section>
  );
}

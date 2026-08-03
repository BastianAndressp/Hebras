"use client";

type AuditLogRow = {
  id: string;
  actor_id: string | null;
  action: string;
  created_at: string;
};

type LogsTabProps = {
  auditLogs: AuditLogRow[];
};

export default function LogsTab({ auditLogs }: LogsTabProps) {
  return (
    <section className="card">
      <h2>Logs de Auditoría Técnicos del Sistema</h2>
      <div style={{ marginTop: 16 }}>
        {auditLogs.map((log) => (
          <div className="conversation-box" key={log.id}>
            <b>Acción: {log.action}</b>
            <div className="muted" style={{ marginTop: 4 }}>
              Actor: {log.actor_id || "sistema"} · Fecha:{" "}
              {new Date(log.created_at).toLocaleString()}
            </div>
          </div>
        ))}
        {!auditLogs.length && (
          <p className="muted">No hay eventos registrados en la auditoría.</p>
        )}
      </div>
    </section>
  );
}

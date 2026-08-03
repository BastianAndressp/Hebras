"use client";

type NotificationItem = {
  id: string;
  title: string;
  message: string;
  severity: string;
  is_read: boolean;
  created_at: string;
};

type NotificationsTabProps = {
  notifications: NotificationItem[];
};

export default function NotificationsTab({ notifications }: NotificationsTabProps) {
  return (
    <section className="card">
      <h2>Centro de Alertas & Notificaciones</h2>
      <div style={{ marginTop: 16 }}>
        {notifications.map((n) => (
          <div className="conversation-box" key={n.id}>
            <b>{n.title}</b>
            <p style={{ margin: "4px 0" }}>{n.message}</p>
            <div className="muted">
              Gravedad: <span className="badge badge-handoff">{n.severity}</span> ·{" "}
              {new Date(n.created_at).toLocaleString()}
            </div>
          </div>
        ))}
        {!notifications.length && (
          <p className="muted">No tienes notificaciones pendientes.</p>
        )}
      </div>
    </section>
  );
}

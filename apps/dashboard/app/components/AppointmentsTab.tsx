"use client";

import { FormEvent, useState } from "react";

type Service = {
  id: string;
  name: string;
  duration_minutes: number;
  price: number | null;
  active: boolean;
};

type Appointment = {
  id: string;
  service_id: string;
  customer_name: string;
  customer_phone: string;
  scheduled_start: string;
  scheduled_end: string;
  status: "scheduled" | "canceled" | "completed";
  created_at: string;
};

type AppointmentsTabProps = {
  services: Service[];
  appointments: Appointment[];
  onCreateService: (service: { name: string; duration_minutes: number; price: number | null; active: boolean }) => Promise<void>;
  onUpdateService: (id: string, service: { name: string; duration_minutes: number; price: number | null; active: boolean }) => Promise<void>;
  onCancelAppointment: (id: string) => Promise<void>;
};

export default function AppointmentsTab({
  services,
  appointments,
  onCreateService,
  onUpdateService,
  onCancelAppointment,
}: AppointmentsTabProps) {
  const [newName, setNewName] = useState("");
  const [newDuration, setNewDuration] = useState(30);
  const [newPrice, setNewPrice] = useState("");

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await onCreateService({
      name: newName.trim(),
      duration_minutes: newDuration,
      price: newPrice ? Number(newPrice) : null,
      active: true,
    });
    setNewName("");
    setNewDuration(30);
    setNewPrice("");
  };

  const formatDateTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
    } catch {
      return iso;
    }
  };

  return (
    <>
      <section className="card">
        <h2>Servicios agendables</h2>
        <p className="muted">
          El bot solo ofrece agendar citas si hay al menos un servicio activo acá. Sin
          servicios configurados, el bot conversa normal pero nunca intenta reservar nada.
        </p>
        <form onSubmit={handleCreate} className="form-grid">
          <div>
            <label>Nombre del servicio</label>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Ej: Corte de pelo" />
          </div>
          <div>
            <label>Duración (minutos)</label>
            <input
              type="number"
              min={5}
              max={480}
              value={newDuration}
              onChange={(e) => setNewDuration(+e.target.value)}
            />
          </div>
          <div>
            <label>Precio (opcional)</label>
            <input type="number" min={0} value={newPrice} onChange={(e) => setNewPrice(e.target.value)} placeholder="10000" />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button type="submit">Agregar servicio</button>
          </div>
        </form>

        <div style={{ marginTop: 20 }}>
          {services.map((s) => (
            <div className="conversation-box" key={s.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <b>{s.name}</b>
                <div className="muted" style={{ marginTop: 4, fontSize: 13 }}>
                  {s.duration_minutes} min{s.price ? ` · $${s.price}` : ""}
                </div>
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() => onUpdateService(s.id, { name: s.name, duration_minutes: s.duration_minutes, price: s.price, active: !s.active })}
              >
                {s.active ? "Desactivar" : "Activar"}
              </button>
            </div>
          ))}
          {!services.length && <p className="muted">Todavía no configuraste ningún servicio.</p>}
        </div>
      </section>

      <section className="card" style={{ marginTop: 20 }}>
        <h2>Citas agendadas</h2>
        {appointments.map((a) => {
          const service = services.find((s) => s.id === a.service_id);
          return (
            <div className="conversation-box" key={a.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <b>{a.customer_name}</b> · {service?.name || "Servicio"}
                <div className="muted" style={{ marginTop: 4, fontSize: 13 }}>
                  {formatDateTime(a.scheduled_start)} · +{a.customer_phone}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  className={`badge-mini ${a.status === "scheduled" ? "badge-active" : a.status === "canceled" ? "badge-closed" : "badge-handoff"}`}
                >
                  {a.status === "scheduled" ? "Agendada" : a.status === "canceled" ? "Cancelada" : "Completada"}
                </span>
                {a.status === "scheduled" && (
                  <button type="button" className="secondary" onClick={() => onCancelAppointment(a.id)}>
                    Cancelar
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {!appointments.length && <p className="muted">Todavía no hay citas agendadas.</p>}
      </section>
    </>
  );
}

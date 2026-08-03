"use client";

import { FormEvent } from "react";

type TeamMember = {
  id: string;
  user_id: string;
  role: string;
  created_at: string;
};

type TeamTabProps = {
  teamMembers: TeamMember[];
  newMemberId: string;
  setNewMemberId: (id: string) => void;
  newMemberRole: string;
  setNewMemberRole: (role: string) => void;
  onAddMember: (e: FormEvent) => void;
  onUpdateRole: (userId: string, role: string) => void;
  onRemoveMember: (userId: string) => void;
};

export default function TeamTab({
  teamMembers,
  newMemberId,
  setNewMemberId,
  newMemberRole,
  setNewMemberRole,
  onAddMember,
  onUpdateRole,
  onRemoveMember,
}: TeamTabProps) {
  return (
    <section className="card">
      <h2>Usuarios del Tenant & Permisos</h2>
      <form onSubmit={onAddMember} className="form-grid">
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <label style={{ margin: "14px 0 6px" }}>UUID / ID del Usuario</label>
            <button
              type="button"
              className="secondary"
              style={{ padding: "4px 10px", fontSize: "11px" }}
              onClick={() => setNewMemberId(typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d")}
            >
              🎲 Generar UUID
            </button>
          </div>
          <input
            value={newMemberId}
            onChange={(e) => setNewMemberId(e.target.value)}
            placeholder="Ingresa o genera un UUID"
          />
        </div>
        <div>
          <label>Rol de Acceso</label>
          <select
            value={newMemberRole}
            onChange={(e) => setNewMemberRole(e.target.value)}
          >
            <option value="staff">staff (Operador)</option>
            <option value="owner">owner (Administrador)</option>
            <option value="solo-lectura">solo-lectura (Auditor)</option>
          </select>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button>Agregar Miembro</button>
        </div>
      </form>

      <div style={{ marginTop: 24 }}>
        {teamMembers.map((member) => (
          <div className="conversation-box" key={member.id}>
            <b>Usuario: {member.user_id}</b>
            <div className="muted" style={{ marginTop: 4 }}>
              Rol actual: <b>{member.role}</b> · Creado: {new Date(member.created_at).toLocaleDateString()}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <select
                value={member.role}
                onChange={(e) => onUpdateRole(member.user_id, e.target.value)}
                style={{ maxWidth: 160 }}
              >
                <option value="staff">staff</option>
                <option value="owner">owner</option>
                <option value="solo-lectura">solo-lectura</option>
              </select>
              <button
                type="button"
                className="secondary"
                onClick={() => onRemoveMember(member.user_id)}
              >
                Eliminar
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

"use client";

import { FormEvent } from "react";

type SettingsData = {
  business_hours_enabled: boolean;
  business_hours: any;
  out_of_hours_message: string;
  monthly_spending_limit_usd: number;
  default_language: string;
};

type ProfileTabProps = {
  companyId: string;
  settingsData: SettingsData;
  setSettingsData: (settings: SettingsData) => void;
  onSave: (e: FormEvent) => void;
};

export default function ProfileTab({
  companyId,
  settingsData,
  setSettingsData,
  onSave,
}: ProfileTabProps) {
  return (
    <form className="card" onSubmit={onSave}>
      <h2>Perfil de la Empresa & Configuración de Cuenta</h2>
      <div className="form-grid">
        <div>
          <label>ID del Tenant (Company ID)</label>
          <input value={companyId || "Cargando..."} disabled />
        </div>
        <div>
          <label>Idioma Predeterminado</label>
          <select
            value={settingsData.default_language}
            onChange={(e) =>
              setSettingsData({
                ...settingsData,
                default_language: e.target.value,
              })
            }
          >
            <option value="es">Español</option>
            <option value="en">English</option>
            <option value="pt">Português</option>
          </select>
        </div>
      </div>
      <button style={{ marginTop: 20 }}>Guardar Configuración</button>
    </form>
  );
}

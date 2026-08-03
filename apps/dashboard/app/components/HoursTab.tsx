"use client";

import { FormEvent } from "react";

type SettingsData = {
  business_hours_enabled: boolean;
  business_hours: any;
  out_of_hours_message: string;
  monthly_spending_limit_usd: number;
  default_language: string;
};

type HoursTabProps = {
  settingsData: SettingsData;
  setSettingsData: (settings: SettingsData) => void;
  onSave: (e: FormEvent) => void;
};

export default function HoursTab({
  settingsData,
  setSettingsData,
  onSave,
}: HoursTabProps) {
  return (
    <form className="card" onSubmit={onSave}>
      <h2>Ventanas de Atención & Horarios Laborales</h2>
      <div className="toggle-container">
        <input
          type="checkbox"
          id="bh-toggle"
          style={{ width: "auto" }}
          checked={settingsData.business_hours_enabled}
          onChange={(e) =>
            setSettingsData({
              ...settingsData,
              business_hours_enabled: e.target.checked,
            })
          }
        />
        <label htmlFor="bh-toggle" style={{ margin: 0, cursor: "pointer" }}>
          Activar Control de Horario Laboral (Responder mensaje de ausencia fuera de horario)
        </label>
      </div>

      <label>Mensaje Automático de Ausencia</label>
      <textarea
        value={settingsData.out_of_hours_message}
        onChange={(e) =>
          setSettingsData({
            ...settingsData,
            out_of_hours_message: e.target.value,
          })
        }
      />
      <button style={{ marginTop: 20 }}>Guardar Horarios</button>
    </form>
  );
}

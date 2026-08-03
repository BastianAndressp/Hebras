"use client";

import { FormEvent } from "react";

type Bot = {
  name: string;
  phone_number_id: string;
  system_prompt: string;
  model: string;
  fallback_model?: string;
  temperature: number;
  max_tokens: number;
  status: string;
};

type WebhookInfo = {
  webhook_url: string;
  verify_token: string;
} | null;

type WhatsAppTabProps = {
  bot: Bot;
  setBot: (bot: Bot) => void;
  onSave: (e: FormEvent) => void;
  webhookInfo?: WebhookInfo;
};

function CopyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label>{label}</label>
      <div style={{ display: "flex", gap: 8 }}>
        <input value={value} readOnly onFocus={(e) => e.target.select()} />
        <button
          type="button"
          className="secondary"
          onClick={() => navigator.clipboard.writeText(value)}
        >
          Copiar
        </button>
      </div>
    </div>
  );
}

export default function WhatsAppTab({ bot, setBot, onSave, webhookInfo = null }: WhatsAppTabProps) {
  return (
    <form className="card" onSubmit={onSave}>
      <h2>Integración WhatsApp Cloud API (Meta)</h2>
      <div className="form-grid">
        <div>
          <label>Phone Number ID (Meta Graph API)</label>
          <input
            value={bot.phone_number_id}
            onChange={(e) => setBot({ ...bot, phone_number_id: e.target.value })}
            placeholder="Ej: 105938482749283"
          />
        </div>
        {webhookInfo ? (
          <>
            <CopyField label="URL de devolución de llamada (Callback URL)" value={webhookInfo.webhook_url} />
            <CopyField label="Identificador de verificación (Verify Token)" value={webhookInfo.verify_token} />
          </>
        ) : (
          <div>
            <label>URL de devolución de llamada (Callback URL)</label>
            <input value="Cargando..." disabled />
          </div>
        )}
      </div>
      <button style={{ marginTop: 16 }}>Guardar Identificador de Meta</button>
      <div className="conversation-box" style={{ marginTop: 20 }}>
        <b>Instrucciones de Vinculación Meta:</b>
        <p className="muted" style={{ margin: "6px 0 0" }}>
          En Meta for Developers → tu app → WhatsApp → Configuración, pega la URL de devolución de llamada y el
          identificador de verificación de arriba. La validación de firmas HMAC-SHA256 asegura que solo mensajes
          autenticados de Meta sean procesados.
        </p>
      </div>
    </form>
  );
}

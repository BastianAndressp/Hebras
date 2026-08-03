"use client";

import { FormEvent } from "react";

type ApiKeysState = {
  has_whatsapp_access_token: boolean;
  has_whatsapp_app_secret: boolean;
  has_openrouter_api_key: boolean;
};

type ApiKeysTabProps = {
  apiKeysState: ApiKeysState;
  newWaToken: string;
  setNewWaToken: (token: string) => void;
  newWaSecret: string;
  setNewWaSecret: (secret: string) => void;
  newOrKey: string;
  setNewOrKey: (key: string) => void;
  onSave: (e: FormEvent) => void;
};

export default function ApiKeysTab({
  apiKeysState,
  newWaToken,
  setNewWaToken,
  newWaSecret,
  setNewWaSecret,
  newOrKey,
  setNewOrKey,
  onSave,
}: ApiKeysTabProps) {
  return (
    <form className="card" onSubmit={onSave}>
      <h2>Configuración de Credenciales externas & API Keys</h2>
      <p className="muted">
        Gestiona tus claves de API cifradas por tenant.
      </p>
      <div className="form-grid">
        <div>
          <label>WhatsApp Cloud Access Token</label>
          <input
            type="password"
            placeholder={apiKeysState.has_whatsapp_access_token ? "•••••••• (Configurado)" : "Ingresa Token..."}
            value={newWaToken}
            onChange={(e) => setNewWaToken(e.target.value)}
          />
        </div>
        <div>
          <label>Meta App Secret (Para firma HMAC)</label>
          <input
            type="password"
            placeholder={apiKeysState.has_whatsapp_app_secret ? "•••••••• (Configurado)" : "Ingresa Secret..."}
            value={newWaSecret}
            onChange={(e) => setNewWaSecret(e.target.value)}
          />
        </div>
        <div>
          <label>OpenRouter API Key Personalizada</label>
          <input
            type="password"
            placeholder={apiKeysState.has_openrouter_api_key ? "•••••••• (Configurado)" : "sk-or-v1-..."}
            value={newOrKey}
            onChange={(e) => setNewOrKey(e.target.value)}
          />
        </div>
      </div>
      <button style={{ marginTop: 20 }}>Guardar Credenciales Cifradas</button>
    </form>
  );
}

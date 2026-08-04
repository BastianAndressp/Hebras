"use client";

import { FormEvent, useState } from "react";

type Bot = {
  id?: string;
  name: string;
  phone_number_id: string;
  system_prompt: string;
  model: string;
  fallback_model?: string;
  temperature: number;
  max_tokens: number;
  status: string;
};

type BotConfigTabProps = {
  bot: Bot;
  setBot: (bot: Bot) => void;
  onSave: (e: FormEvent) => void;
  bots?: Bot[];
  onCreateBot?: (data: { name: string; phone_number_id: string }) => Promise<void> | void;
  onDeleteBot?: (botId: string) => Promise<void> | void;
};

export default function BotConfigTab({
  bot,
  setBot,
  onSave,
  bots = [],
  onCreateBot,
  onDeleteBot,
}: BotConfigTabProps) {
  const [newBotName, setNewBotName] = useState("");
  const [newBotPhoneId, setNewBotPhoneId] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreateBot = async (e: FormEvent) => {
    e.preventDefault();
    if (!onCreateBot || !newBotName.trim() || !newBotPhoneId.trim()) return;
    setCreating(true);
    try {
      await onCreateBot({ name: newBotName.trim(), phone_number_id: newBotPhoneId.trim() });
      setNewBotName("");
      setNewBotPhoneId("");
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      {(onCreateBot || bots.length > 0) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Mis Bots</h2>
          <p className="muted" style={{ marginBottom: 12 }}>
            Cada bot tiene su propio número de WhatsApp, prompt, base de conocimiento y horarios.
          </p>
          {bots.length > 0 && (
            <table style={{ width: "100%", marginBottom: 16 }}>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Número (phone_number_id)</th>
                  <th>Estado</th>
                  {onDeleteBot && <th></th>}
                </tr>
              </thead>
              <tbody>
                {bots.map((b) => (
                  <tr key={b.id}>
                    <td>{b.name}</td>
                    <td>{b.phone_number_id}</td>
                    <td>
                      <span className={`badge ${b.status === "active" ? "badge-active" : "badge-error"}`}>
                        {b.status}
                      </span>
                    </td>
                    {onDeleteBot && (
                      <td>
                        <button
                          type="button"
                          className="secondary"
                          disabled={bots.length <= 1}
                          title={bots.length <= 1 ? "No puedes eliminar el único bot" : "Eliminar bot"}
                          onClick={() => b.id && onDeleteBot(b.id)}
                        >
                          Eliminar
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {onCreateBot && (
            <form onSubmit={handleCreateBot} className="form-grid">
              <div>
                <label>Nombre del nuevo bot</label>
                <input
                  value={newBotName}
                  onChange={(e) => setNewBotName(e.target.value)}
                  placeholder="Ej: Bot de Ventas"
                />
              </div>
              <div>
                <label>Número de WhatsApp (phone_number_id de Meta)</label>
                <input
                  value={newBotPhoneId}
                  onChange={(e) => setNewBotPhoneId(e.target.value)}
                  placeholder="1029384756"
                />
              </div>
              <div style={{ alignSelf: "end" }}>
                <button disabled={creating}>{creating ? "Creando..." : "Crear bot"}</button>
              </div>
            </form>
          )}
        </div>
      )}

      <form className="card" onSubmit={onSave}>
        <h2>Configuración de Inteligencia Artificial</h2>
        <div className="form-grid">
          <div>
            <label>Nombre del Asistente</label>
            <input
              value={bot.name}
              onChange={(e) => setBot({ ...bot, name: e.target.value })}
            />
          </div>
          <div>
            <label>Modelo LLM Principal (OpenRouter)</label>
            <select
              value={bot.model}
              onChange={(e) => setBot({ ...bot, model: e.target.value })}
            >
              <option value="qwen/qwen3-30b-a3b-instruct-2507">Qwen3 30B A3B (Mejor calidad/precio)</option>
              <option value="openai/gpt-oss-120b">GPT-OSS 120B (El más económico)</option>
              <option value="deepseek/deepseek-chat">DeepSeek V3 (Económico / Rápido)</option>
              <option value="qwen/qwen-2.5-72b-instruct">Qwen 2.5 72B (Alta precisión)</option>
              <option value="moonshotai/kimi-k2.5">Kimi K2.5 (Contexto largo, económico)</option>
              <option value="meta-llama/llama-3.3-70b-instruct">Llama 3.3 70B</option>
            </select>
          </div>
          <div>
            <label>Modelo de Respaldo (Fallback)</label>
            <input
              value={bot.fallback_model || ""}
              onChange={(e) => setBot({ ...bot, fallback_model: e.target.value })}
              placeholder="meta-llama/llama-3.3-70b-instruct"
            />
          </div>
          <div>
            <label>Temperatura ({bot.temperature})</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={bot.temperature}
              onChange={(e) => setBot({ ...bot, temperature: +e.target.value })}
            />
          </div>
          <div>
            <label>Tokens Máximos por Respuesta</label>
            <input
              type="number"
              min="50"
              max="500"
              value={bot.max_tokens}
              onChange={(e) => setBot({ ...bot, max_tokens: +e.target.value })}
            />
          </div>
        </div>
        <button style={{ marginTop: 20 }}>Guardar Parámetros de IA</button>
      </form>
    </>
  );
}

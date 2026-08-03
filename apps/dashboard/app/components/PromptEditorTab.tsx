"use client";

import { FormEvent, useState } from "react";

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

type PromptEditorTabProps = {
  bot: Bot;
  setBot: (bot: Bot) => void;
  onSave: (e: FormEvent) => void;
};

const RUBRO_TEMPLATES: Record<string, string> = {
  retail:
    "Eres un asistente virtual amable y eficiente para una tienda de Retail. Tu objetivo es ayudar a los clientes a encontrar productos, consultar precios, disponibilidad de stock y políticas de envío o devoluciones. Sé conciso y directo.",
  clinica:
    "Eres el asistente de atención al paciente de una Clínica Médica y Dental. Responde con tono empático, formal y profesional. Brinda información sobre horarios de atención, especialidades, ubicación y preparación para consultas.",
  inmobiliaria:
    "Eres un asesor inmobiliario virtual. Tu objetivo es calificar prospectos interesados en comprar o alquilar propiedades, brindar información sobre proyectos disponibles, precios y agendar visitas.",
  restaurante:
    "Eres el asistente de un Restaurante. Ayuda a los clientes a consultar el menú del día, horarios, ubicación, opciones de reserva de mesa y tomar pedidos de delivery.",
  servicios:
    "Eres el asistente comercial de una empresa de Servicios Profesionales. Tu objetivo es explicar los servicios ofrecidos, responder preguntas frecuentes y coordinar una reunión de asesoría inicial.",
};

export default function PromptEditorTab({ bot, setBot, onSave }: PromptEditorTabProps) {
  const [selectedRubro, setSelectedRubro] = useState("retail");

  const applyTemplate = () => {
    if (RUBRO_TEMPLATES[selectedRubro]) {
      setBot({ ...bot, system_prompt: RUBRO_TEMPLATES[selectedRubro] });
    }
  };

  return (
    <form className="card" onSubmit={onSave}>
      <h2>System Prompt & Plantillas por Rubro</h2>
      <p className="muted">
        Define la personalidad, límites e instrucciones del bot. Puedes partir desde una plantilla optimizada por industria.
      </p>
      <div style={{ display: "flex", gap: 12, margin: "16px 0" }}>
        <select
          value={selectedRubro}
          onChange={(e) => setSelectedRubro(e.target.value)}
          style={{ maxWidth: 300 }}
        >
          <option value="retail">Retail / Comercio</option>
          <option value="clinica">Clínica Médica / Dental</option>
          <option value="inmobiliaria">Inmobiliaria / Ventas</option>
          <option value="restaurante">Restaurante / Delivery</option>
          <option value="servicios">Servicios Profesionales</option>
        </select>
        <button type="button" className="secondary" onClick={applyTemplate}>
          Cargar Plantilla
        </button>
      </div>
      <label>Instrucciones del Sistema (System Prompt)</label>
      <textarea
        value={bot.system_prompt}
        onChange={(e) => setBot({ ...bot, system_prompt: e.target.value })}
        rows={10}
      />
      <button style={{ marginTop: 20 }}>Guardar Prompt</button>
    </form>
  );
}

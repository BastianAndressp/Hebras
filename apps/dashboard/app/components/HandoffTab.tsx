"use client";

import { FormEvent, useState } from "react";

type Rule = {
  keywords: string[];
  max_bot_attempts: number;
  notification_email?: string;
  ai_handoff_phrase?: string | null;
};

type HandoffTabProps = {
  rule: Rule;
  setRule: (rule: Rule) => void;
  onSave: (e: FormEvent) => void;
};

export default function HandoffTab({ rule, setRule, onSave }: HandoffTabProps) {
  // Estado local para el texto tal cual se escribe: si el input mostrara
  // rule.keywords.join(", ") directamente, cada coma o espacio se "comía" al instante
  // porque el onChange recalculaba el arreglo (filtrando vacíos) y eso volvía a pintar
  // el input ya "limpio" en cada tecla. El arreglo (lo que se guarda) sigue
  // actualizándose en cada cambio; solo el texto visible queda desacoplado de él.
  const [keywordsText, setKeywordsText] = useState(rule.keywords.join(", "));

  const handleKeywordsChange = (value: string) => {
    setKeywordsText(value);
    setRule({
      ...rule,
      keywords: value
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
    });
  };

  return (
    <form className="card" onSubmit={onSave}>
      <h2>Reglas de Escalación y Derivación a Humano</h2>
      <label>Palabras Clave de Traspaso (Separadas por coma)</label>
      <input
        value={keywordsText}
        onChange={(e) => handleKeywordsChange(e.target.value)}
      />
      <label>Máximo de Intentos Fallidos del Bot</label>
      <input
        type="number"
        min="1"
        max="10"
        value={rule.max_bot_attempts}
        onChange={(e) =>
          setRule({ ...rule, max_bot_attempts: +e.target.value })
        }
      />
      <label>Correo Electrónico para Notificaciones de Handoff</label>
      <input
        type="email"
        value={rule.notification_email || ""}
        onChange={(e) =>
          setRule({ ...rule, notification_email: e.target.value })
        }
      />
      <label>Frase de Derivación de la IA</label>
      <input
        placeholder='Ej: "Te paso con un trabajador de Basfer para que te ayude directamente."'
        value={rule.ai_handoff_phrase || ""}
        onChange={(e) =>
          setRule({ ...rule, ai_handoff_phrase: e.target.value })
        }
      />
      <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
        Si la respuesta que genera la IA contiene esta frase exacta, la conversación pasa
        automáticamente a modo Humano. Debe coincidir con lo que tu prompt le indica decir
        a la IA cuando decide derivar. Déjalo vacío para desactivar esta regla.
      </p>
      <button style={{ marginTop: 20 }}>Guardar Reglas de Derivación</button>
    </form>
  );
}

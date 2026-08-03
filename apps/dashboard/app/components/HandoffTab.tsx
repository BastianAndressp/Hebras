"use client";

import { FormEvent } from "react";

type Rule = {
  keywords: string[];
  max_bot_attempts: number;
  notification_email?: string;
};

type HandoffTabProps = {
  rule: Rule;
  setRule: (rule: Rule) => void;
  onSave: (e: FormEvent) => void;
};

export default function HandoffTab({ rule, setRule, onSave }: HandoffTabProps) {
  return (
    <form className="card" onSubmit={onSave}>
      <h2>Reglas de Escalación y Derivación a Humano</h2>
      <label>Palabras Clave de Traspaso (Separadas por coma)</label>
      <input
        value={rule.keywords.join(", ")}
        onChange={(e) =>
          setRule({
            ...rule,
            keywords: e.target.value
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean),
          })
        }
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
      <button style={{ marginTop: 20 }}>Guardar Reglas de Derivación</button>
    </form>
  );
}

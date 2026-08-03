"use client";

type TabNavigationProps = {
  activeTab: string;
  onSelectTab: (tabId: string) => void;
};

export const TAB_LIST: [string, string][] = [
  ["resumen", "Resumen"],
  ["inbox", "Inbox"],
  ["bot", "Config IA"],
  ["prompt", "Prompt"],
  ["conocimiento", "Documentos RAG"],
  ["estadisticas", "Estadísticas"],
  ["equipo", "Equipo"],
  ["facturacion", "Facturación"],
  ["whatsapp", "WhatsApp Meta"],
  ["apikeys", "API Keys / OpenRouter"],
  ["horarios", "Horarios"],
  ["derivacion", "Derivación"],
  ["logs", "Logs"],
  ["notificaciones", "Notificaciones"],
  ["perfil", "Perfil"],
];

export default function TabNavigation({ activeTab, onSelectTab }: TabNavigationProps) {
  return (
    <nav className="tabs">
      {TAB_LIST.map(([id, label]) => (
        <button
          key={id}
          className={`tab-btn ${activeTab === id ? "active" : ""}`}
          onClick={() => onSelectTab(id)}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}

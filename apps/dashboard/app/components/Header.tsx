"use client";

type BotOption = {
  id?: string;
  name: string;
  phone_number_id: string;
  status: string;
};

type HeaderProps = {
  phone_number_id: string;
  status: string;
  onLogout: () => void;
  bots?: BotOption[];
  selectedBotId?: string;
  onSelectBot?: (botId: string) => void;
};

export default function Header({
  phone_number_id,
  status,
  onLogout,
  bots = [],
  selectedBotId = "",
  onSelectBot,
}: HeaderProps) {
  return (
    <header className="header-container">
      <div className="brand-title">
        <div className="brand-logo">H</div>
        <div>
          <h1>Hebras</h1>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
            Número: <b>{phone_number_id}</b> ·{" "}
            <span className={`badge ${status === "active" ? "badge-active" : "badge-error"}`}>
              {status}
            </span>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {bots.length > 1 && onSelectBot && (
          <select
            value={selectedBotId}
            onChange={(e) => onSelectBot(e.target.value)}
            style={{ maxWidth: 220 }}
            title="Cambiar de bot"
          >
            {bots.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.phone_number_id})
              </option>
            ))}
          </select>
        )}
        <button className="secondary" onClick={onLogout}>
          Cerrar Sesión
        </button>
      </div>
    </header>
  );
}

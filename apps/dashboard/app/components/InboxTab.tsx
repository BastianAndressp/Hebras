"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Message = {
  direction: "inbound" | "outbound";
  content: string;
  created_at?: string;
};

type Conversation = {
  id: string;
  contact_phone: string;
  status: "active" | "handoff" | "closed";
  last_message_at?: string;
  messages: Message[];
};

type InboxTabProps = {
  conversations: Conversation[];
  convFilter: string;
  setConvFilter: (filter: string) => void;
  onToggleStatus?: (conversationId: string, newStatus: string) => Promise<void>;
  onSendMessage?: (conversationId: string, content: string) => Promise<void>;
};

export default function InboxTab({
  conversations,
  convFilter,
  setConvFilter,
  onToggleStatus,
  onSendMessage,
}: InboxTabProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [messageText, setMessageText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Filter conversations by tab filter & search query
  const filteredConversations = conversations.filter((c) => {
    if (convFilter === "active" && c.status !== "active") return false;
    if (convFilter === "handoff" && c.status !== "handoff") return false;
    if (convFilter === "closed" && c.status !== "closed") return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const phoneMatch = c.contact_phone.toLowerCase().includes(q);
      const msgMatch = c.messages.some((m) => m.content.toLowerCase().includes(q));
      return phoneMatch || msgMatch;
    }
    return true;
  });

  // Select first conversation if none selected
  useEffect(() => {
    if (!selectedId && filteredConversations.length > 0) {
      setSelectedId(filteredConversations[0].id);
    } else if (selectedId && !conversations.some((c) => c.id === selectedId)) {
      if (filteredConversations.length > 0) {
        setSelectedId(filteredConversations[0].id);
      } else {
        setSelectedId(null);
      }
    }
  }, [conversations, filteredConversations, selectedId]);

  const activeConv = conversations.find((c) => c.id === selectedId);

  // Auto scroll to bottom solo cuando realmente hay un mensaje nuevo (cambia la
  // cantidad) o se selecciona otra conversación -- no en cada refresco del polling del
  // Inbox (cada 4s), que trae un arreglo nuevo aunque el contenido no haya cambiado y
  // antes disparaba un scroll de igual forma, empujando la página hacia abajo sola.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConv?.messages?.length, selectedId]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedId || !messageText.trim() || isSending || !onSendMessage) return;
    try {
      setIsSending(true);
      await onSendMessage(selectedId, messageText.trim());
      setMessageText("");
    } finally {
      setIsSending(false);
    }
  };

  const handleToggleMode = async (newStatus: "active" | "handoff" | "closed") => {
    if (!selectedId || !onToggleStatus) return;
    await onToggleStatus(selectedId, newStatus);
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <section className="card chat-split-card" style={{ padding: 0, overflow: "hidden" }}>
      <div className="chat-split-container">
        {/* LEFT PANEL: Conversation List */}
        <div className="chat-sidebar">
          {/* Header & Filter tabs */}
          <div className="chat-sidebar-header">
            <h3>Inbox de Conversaciones</h3>
            <div className="chat-filter-pills">
              {[
                { id: "all", label: "Todas" },
                { id: "active", label: "🤖 IA" },
                { id: "handoff", label: "👤 Humano" },
                { id: "closed", label: "Cerradas" },
              ].map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`pill-btn ${convFilter === f.id ? "active" : ""}`}
                  onClick={() => setConvFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <div style={{ marginTop: 10 }}>
              <input
                type="text"
                placeholder="🔍 Buscar por número o mensaje..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: "100%", fontSize: 13, padding: "8px 12px" }}
              />
            </div>
          </div>

          {/* Conversations List */}
          <div className="chat-sidebar-list">
            {filteredConversations.map((c) => {
              const lastMsg = c.messages[c.messages.length - 1];
              const isSelected = c.id === selectedId;
              return (
                <div
                  key={c.id}
                  className={`chat-item ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedId(c.id)}
                >
                  <div className="chat-avatar">📱</div>
                  <div className="chat-item-info">
                    <div className="chat-item-header">
                      <span className="chat-phone">+{c.contact_phone}</span>
                      <span className="chat-time">
                        {formatTime(lastMsg?.created_at || c.last_message_at)}
                      </span>
                    </div>
                    <div className="chat-item-sub">
                      <span className="chat-preview">
                        {lastMsg ? (
                          <>
                            {lastMsg.direction === "outbound" ? "Tú: " : ""}
                            {lastMsg.content}
                          </>
                        ) : (
                          <span className="muted">Sin mensajes</span>
                        )}
                      </span>
                      <span
                        className={`badge-mini ${
                          c.status === "active"
                            ? "badge-active"
                            : c.status === "handoff"
                            ? "badge-handoff"
                            : "badge-closed"
                        }`}
                      >
                        {c.status === "active" ? "🤖 IA" : c.status === "handoff" ? "👤 Humano" : "🔒 Cerrado"}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}

            {!filteredConversations.length && (
              <div style={{ padding: 24, textAlign: "center" }} className="muted">
                No hay conversaciones en esta categoría.
              </div>
            )}
          </div>
        </div>

        {/* RIGHT PANEL: Open Conversation */}
        <div className="chat-main">
          {activeConv ? (
            <>
              {/* Chat Header */}
              <div className="chat-main-header">
                <div className="chat-user-details">
                  <div className="chat-avatar-lg">📱</div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 16 }}>+{activeConv.contact_phone}</h3>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {activeConv.status === "active"
                        ? "🤖 IA respondiendo en tiempo real"
                        : activeConv.status === "handoff"
                        ? "👤 Atención humana activa (IA pausada)"
                        : "🔒 Conversación cerrada"}
                    </span>
                  </div>
                </div>

                {/* Control Options: Toggle Mode IA / Humano */}
                <div className="chat-mode-toggle">
                  <div className="toggle-button-group">
                    <button
                      type="button"
                      className={`toggle-btn ${activeConv.status === "active" ? "btn-ia-active" : "secondary"}`}
                      onClick={() => handleToggleMode("active")}
                      title="Permitir que la IA responda automáticamente"
                    >
                      🤖 Responder con IA
                    </button>
                    <button
                      type="button"
                      className={`toggle-btn ${activeConv.status === "handoff" ? "btn-human-active" : "secondary"}`}
                      onClick={() => handleToggleMode("handoff")}
                      title="Pausar IA y tomar control humano de la conversación"
                    >
                      👤 Derivar a Humano
                    </button>
                  </div>

                  {activeConv.status !== "closed" && (
                    <button
                      type="button"
                      className="secondary"
                      style={{ fontSize: 12, padding: "6px 10px" }}
                      onClick={() => handleToggleMode("closed")}
                    >
                      🔒 Cerrar
                    </button>
                  )}
                </div>
              </div>

              {/* Chat Messages Feed */}
              <div className="chat-feed">
                {activeConv.messages.map((m, idx) => (
                  <div
                    key={idx}
                    className={`message-wrapper ${m.direction === "outbound" ? "outbound" : "inbound"}`}
                  >
                    <div className="message-box">
                      <div className="message-sender">
                        {m.direction === "outbound"
                          ? activeConv.status === "handoff"
                            ? "👤 Agente Humano"
                            : "🤖 Bot / Asistente IA"
                          : `📱 +${activeConv.contact_phone}`}
                      </div>
                      <div className="message-text">{m.content}</div>
                      <div className="message-meta">
                        {formatTime(m.created_at)}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Chat Input Bar */}
              <form className="chat-input-bar" onSubmit={handleSend}>
                <div className="chat-mode-indicator">
                  {activeConv.status === "handoff" ? (
                    <span className="mode-tag tag-human">
                      👤 Estás en modo Humano — La IA NO responderá automáticamente.
                    </span>
                  ) : activeConv.status === "active" ? (
                    <span className="mode-tag tag-ia">
                      🤖 Modo IA activo — Si envías un mensaje manual, la conversación cambiará a humano.
                    </span>
                  ) : (
                    <span className="mode-tag tag-closed">
                      🔒 Conversación cerrada. Al enviar un mensaje se reabrirá.
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="text"
                    placeholder="Escribe una respuesta para enviar por WhatsApp..."
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    disabled={isSending}
                    style={{ flex: 1, padding: "10px 14px", borderRadius: 8, fontSize: 14 }}
                  />
                  <button type="submit" disabled={isSending || !messageText.trim()}>
                    {isSending ? "Enviando..." : "🚀 Enviar"}
                  </button>
                </div>
              </form>
            </>
          ) : (
            <div className="chat-empty-state">
              <div style={{ fontSize: 48 }}>💬</div>
              <h3>Selecciona una conversación</h3>
              <p className="muted">Elige un contacto de la lista izquierda para chatear en vivo.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

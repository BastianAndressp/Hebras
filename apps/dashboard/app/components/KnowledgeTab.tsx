"use client";

import { FormEvent } from "react";

type DocumentRow = {
  id: string;
  title: string;
  status: string;
  chunk_count: number;
  created_at: string;
};

type KnowledgeTabProps = {
  documents: DocumentRow[];
  documentTitle: string;
  setDocumentTitle: (title: string) => void;
  documentContent: string;
  setDocumentContent: (content: string) => void;
  documentFile: File | null;
  setDocumentFile: (file: File | null) => void;
  onSave: (e: FormEvent) => void;
};

export default function KnowledgeTab({
  documents,
  documentTitle,
  setDocumentTitle,
  documentContent,
  setDocumentContent,
  documentFile,
  setDocumentFile,
  onSave,
}: KnowledgeTabProps) {
  return (
    <section className="card">
      <h2>Base de Conocimiento (RAG Vectorial con pgvector)</h2>
      <p className="muted">
        Sube catálogos, listas de precios o documentos FAQ en PDF, Word o TXT. El sistema los fragmenta y los vectoriza para respuestas semánticas precisas.
      </p>
      <form onSubmit={onSave} style={{ marginTop: 20 }}>
        <label>Título del Documento</label>
        <input
          value={documentTitle}
          onChange={(e) => setDocumentTitle(e.target.value)}
          placeholder="Catálogo 2026 / Preguntas Frecuentes"
        />
        <label>Subir Archivo (.pdf, .docx, .txt, .md)</label>
        <input
          type="file"
          accept=".pdf,.docx,.txt,.md,.csv"
          onChange={(e) => setDocumentFile(e.target.files?.[0] ?? null)}
        />
        <label>O ingresar Texto Plano Manual</label>
        <textarea
          value={documentContent}
          onChange={(e) => setDocumentContent(e.target.value)}
          placeholder="Pega aquí información relevante si no subirás un archivo..."
        />
        <button style={{ marginTop: 16 }}>
          {documentFile ? "Subir e Indexar con pgvector" : "Guardar Documento"}
        </button>
      </form>

      <div style={{ marginTop: 28 }}>
        <h3>Documentos Cargados</h3>
        {documents.map((doc) => (
          <div className="conversation-box" key={doc.id}>
            <b>{doc.title}</b>
            <div className="muted" style={{ marginTop: 4 }}>
              Estado: <span className="badge badge-active">{doc.status}</span> · {doc.chunk_count} fragmentos vectorizados
            </div>
          </div>
        ))}
        {!documents.length && <p className="muted">No hay documentos en la base de conocimiento.</p>}
      </div>
    </section>
  );
}

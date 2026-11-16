import { useEffect, useRef, useState } from "react";
import { ask, deleteDocument, listDocuments, uploadPdf } from "./api.js";

function Sources({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources?.length) return null;
  return (
    <div className="sources">
      <button className="link" onClick={() => setOpen(!open)} aria-expanded={open}>
        {open ? "Hide" : "Show"} {sources.length} sources
      </button>
      {open && (
        <ul>
          {sources.map((s, i) => (
            <li key={i}>
              <span className="cite">
                {s.filename}, page {s.page}
              </span>
              <p>{s.snippet}…</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function App() {
  const [docs, setDocs] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef(null);
  const endRef = useRef(null);

  const refresh = () => listDocuments().then(setDocs).catch((e) => setError(e.message));
  useEffect(() => { refresh(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  async function handleFiles(files) {
    setError("");
    setUploading(true);
    for (const file of files) {
      try { await uploadPdf(file); } catch (e) { setError(`${file.name}: ${e.message}`); }
    }
    setUploading(false);
    refresh();
  }

  async function send(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || busy) return;
    setQuestion("");
    setError("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const res = await ask(q);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, sources: res.sources }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <aside className="side">
        <h1>Knowledge Assistant</h1>
        <div
          className={`drop ${dragging ? "on" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles([...e.dataTransfer.files]); }}
        >
          <p>{uploading ? "Indexing your PDF…" : "Drop PDFs here"}</p>
          <button onClick={() => fileRef.current.click()} disabled={uploading}>Choose files</button>
          <input ref={fileRef} type="file" accept="application/pdf" multiple hidden
            onChange={(e) => { handleFiles([...e.target.files]); e.target.value = ""; }} />
        </div>
        <h2>Documents</h2>
        {docs.length === 0 ? (
          <p className="muted">No documents yet. Upload a PDF to start asking questions.</p>
        ) : (
          <ul className="docs">
            {docs.map((d) => (
              <li key={d.doc_id}>
                <span title={d.filename}>{d.filename}</span>
                <button className="link" onClick={() => deleteDocument(d.doc_id).then(refresh)}>Remove</button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <main className="chat">
        <div className="thread" aria-live="polite">
          {messages.length === 0 && (
            <p className="muted empty">Ask a question about your documents. Answers cite the page they came from.</p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <p>{m.text}</p>
              <Sources sources={m.sources} />
            </div>
          ))}
          {busy && <div className="msg assistant muted">Searching your documents…</div>}
          <div ref={endRef} />
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        <form onSubmit={send} className="composer">
          <input value={question} onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about your documents" aria-label="Question" />
          <button type="submit" disabled={busy || !question.trim()}>Ask</button>
        </form>
      </main>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import DataExplorer from "./DataExplorer.jsx";
import "./App.css";

const EXAMPLES = [
  {
    mode: "SQL_ONLY",
    label: "Ask the database",
    text: "Which department had the highest revenue last quarter?",
  },
  {
    mode: "DOCUMENT_ONLY",
    label: "Ask the documents",
    text: "What is the company's refund policy?",
  },
  {
    mode: "HYBRID",
    label: "Ask across both",
    text: "Which customers are eligible for refunds according to our policy, and how much did they spend in the last 6 months?",
  },
];

function modeClass(mode) {
  if (mode === "SQL_ONLY") return "badge sql";
  if (mode === "DOCUMENT_ONLY") return "badge docs";
  if (mode === "HYBRID") return "badge hybrid";
  return "badge";
}

function modeLabel(mode) {
  if (mode === "SQL_ONLY") return "Database";
  if (mode === "DOCUMENT_ONLY") return "Documents";
  if (mode === "HYBRID") return "Hybrid";
  return mode;
}

function AssistantCard({ msg }) {
  const [showSql, setShowSql] = useState(false);
  const [copied, setCopied] = useState(false);
  const conf = typeof msg.confidence === "number" ? msg.confidence : null;

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(msg.answer || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  if (msg.error) {
    return (
      <div className="row assistant">
        <div className="avatar">T</div>
        <div className="bubble error">
          <div className="answer">{msg.answer}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="row assistant">
      <div className="avatar">T</div>
      <div className="bubble">
        <div className="card-head">
          {msg.mode && (
            <span className={modeClass(msg.mode)}>{modeLabel(msg.mode)}</span>
          )}
          {conf != null && (
            <span className="conf">
              confidence {(conf * 100).toFixed(0)}%
            </span>
          )}
          {msg.latency_ms != null && (
            <span className="conf">{msg.latency_ms} ms</span>
          )}
          <button type="button" className="ghost" onClick={copyAnswer}>
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        {conf != null && (
          <div className="meter" aria-hidden="true">
            <div style={{ width: `${Math.min(100, Math.max(0, conf * 100))}%` }} />
          </div>
        )}
        <div className="answer">{msg.answer}</div>
        {msg.sql_executed && (
          <details open={showSql} onToggle={(e) => setShowSql(e.target.open)}>
            <summary>SQL executed</summary>
            <pre className="sql">{msg.sql_executed}</pre>
          </details>
        )}
        {msg.chunks_cited?.length > 0 && (
          <details>
            <summary>Citations ({msg.chunks_cited.length})</summary>
            <ul className="cites">
              {msg.chunks_cited.map((c, j) => (
                <li key={j}>
                  <strong>{c.source}</strong>
                  <span>
                    chunk {c.chunk_index} · similarity{" "}
                    {Number(c.similarity).toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState("checking");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tab, setTab] = useState("chat");
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    let cancelled = false;
    async function ping() {
      try {
        const res = await fetch("/health");
        if (!cancelled) setHealth(res.ok ? "online" : "offline");
      } catch {
        if (!cancelled) setHealth("offline");
      }
    }
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  async function send(text) {
    const q = (text ?? question).trim();
    if (!q || busy) return;
    setQuestion("");
    setSidebarOpen(false);
    setTab("chat");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const res = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : res.statusText
        );
      }
      setMessages((m) => [...m, { role: "assistant", ...data }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          answer: `Request failed: ${err.message}`,
          error: true,
        },
      ]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    send();
  }

  function newChat() {
    setMessages([]);
    setQuestion("");
    setSidebarOpen(false);
    inputRef.current?.focus();
  }

  return (
    <div className="app">
      <aside className={sidebarOpen ? "open" : ""}>
        <div className="brand">
          <div className="logo">T</div>
          <div>
            <h1>TalkToDB</h1>
            <p>SQL · documents · hybrid</p>
          </div>
        </div>

        <button type="button" className="new-chat" onClick={newChat}>
          New chat
        </button>
        <button
          type="button"
          className="new-chat"
          onClick={() => {
            setTab("data");
            setSidebarOpen(false);
          }}
        >
          Browse data
        </button>

        <p className="rail-label">Try an example</p>
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.text}
              type="button"
              onClick={() => send(ex.text)}
              disabled={busy}
            >
              <span className={modeClass(ex.mode)}>{modeLabel(ex.mode)}</span>
              <span className="ex-text">{ex.label}</span>
              <span className="ex-q">{ex.text}</span>
            </button>
          ))}
        </div>

        <div className={`status ${health}`}>
          <span className="dot" />
          {health === "online" && "Backend online"}
          {health === "offline" && "Backend offline — start uvicorn"}
          {health === "checking" && "Checking backend…"}
        </div>
      </aside>

      <main>
        <header className="topbar">
          <button
            type="button"
            className="menu"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Toggle sidebar"
          >
            Menu
          </button>
          <nav className="tabs">
            <button
              type="button"
              className={tab === "chat" ? "on" : ""}
              onClick={() => setTab("chat")}
            >
              Chat
            </button>
            <button
              type="button"
              className={tab === "data" ? "on" : ""}
              onClick={() => setTab("data")}
            >
              Data
            </button>
          </nav>
          <span className="topbar-hint">
            {tab === "chat"
              ? "Ask about orders, revenue, or company policy."
              : "Sample tables, charts, and policy documents."}
          </span>
        </header>

        {tab === "data" ? <DataExplorer /> : <>
        <div className="thread">
          {messages.length === 0 && !busy && (
            <div className="empty">
              <h2>What do you want to know?</h2>
              <p>
                TalkToDB routes your question to the database, the policy
                documents, or both, then answers with citations and a confidence
                score.
              </p>
              <div className="empty-actions">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex.mode}
                    type="button"
                    onClick={() => send(ex.text)}
                    disabled={busy}
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) =>
            msg.role === "user" ? (
              <div className="row user" key={i}>
                <div className="bubble user">{msg.text}</div>
                <div className="avatar you">You</div>
              </div>
            ) : (
              <AssistantCard key={i} msg={msg} />
            )
          )}
          {busy && (
            <div className="row assistant">
              <div className="avatar">T</div>
              <div className="bubble muted">Thinking…</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={onSubmit}>
          <textarea
            ref={inputRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about revenue, refunds, shipping, or customers…"
            rows={2}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <button type="submit" disabled={busy || !question.trim()}>
            Send
          </button>
        </form>
        </>}
      </main>
    </div>
  );
}

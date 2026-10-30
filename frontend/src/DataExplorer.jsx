import { useEffect, useMemo, useState } from "react";

const SECTIONS = [
  ["overview", "Overview"],
  ["customers", "Customers"],
  ["orders", "Orders"],
  ["revenue", "Revenue"],
  ["policies", "Policies"],
  ["log", "Query log"],
];

function money(n) {
  const v = Number(n) || 0;
  return v.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function Bar({ value, max, color = "#3b82f6" }) {
  const pct = max > 0 ? Math.max(4, (value / max) * 100) : 0;
  return (
    <div className="bar-track">
      <div className="bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function Table({ columns, rows }) {
  if (!rows?.length) return <p className="muted">No rows.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id ?? row.order_id ?? row.customer_id ?? row.log_id ?? i}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DataExplorer() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [section, setSection] = useState("overview");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch("/data")
      .then(async (res) => {
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail || res.statusText);
        if (!cancelled) setData(body);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const q = filter.trim().toLowerCase();
  const orders = useMemo(() => {
    const rows = data?.orders || [];
    if (!q) return rows;
    return rows.filter((r) =>
      `${r.customer_name} ${r.status} ${r.amount} ${r.order_date}`.toLowerCase().includes(q)
    );
  }, [data, q]);

  const customers = useMemo(() => {
    const rows = data?.customers || [];
    if (!q) return rows;
    return rows.filter((r) =>
      `${r.name} ${r.email}`.toLowerCase().includes(q)
    );
  }, [data, q]);

  if (error) {
    return <div className="data-page"><p className="bubble error">Could not load data: {error}</p></div>;
  }
  if (!data) {
    return <div className="data-page"><p className="muted">Loading sample database…</p></div>;
  }

  const maxSpend = Math.max(...(data.spend_6m || []).map((r) => Number(r.total_spent) || 0), 1);
  const maxRev = Math.max(...(data.revenue || []).map((r) => Number(r.amount) || 0), 1);
  const maxStatus = Math.max(...(data.order_status || []).map((r) => Number(r.n) || 0), 1);
  const policyGroups = {};
  for (const chunk of data.policies || []) {
    (policyGroups[chunk.source_name] ||= []).push(chunk);
  }

  return (
    <div className="data-page">
      <p className="data-note">{data.note}</p>

      <nav className="data-nav">
        {SECTIONS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={section === id ? "on" : ""}
            onClick={() => setSection(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {section === "overview" && (
        <>
          <div className="stat-grid">
            {Object.entries(data.counts).map(([k, v]) => (
              <div className="stat" key={k}>
                <div className="stat-n">{v}</div>
                <div className="stat-l">{k.replace("_", " ")}</div>
              </div>
            ))}
          </div>

          <h3>Order status mix</h3>
          <div className="chart">
            {(data.order_status || []).map((row) => (
              <div className="chart-row" key={row.status}>
                <span className="chart-label">{row.status}</span>
                <Bar
                  value={Number(row.n)}
                  max={maxStatus}
                  color={
                    row.status === "completed"
                      ? "#22c55e"
                      : row.status === "pending"
                        ? "#f59e0b"
                        : "#ef4444"
                  }
                />
                <span className="chart-val">
                  {row.n} · {money(row.total)}
                </span>
              </div>
            ))}
          </div>

          <h3>Spend last 6 months (by customer)</h3>
          <div className="chart">
            {(data.spend_6m || []).map((row) => (
              <div className="chart-row" key={row.customer_id}>
                <span className="chart-label">{row.name}</span>
                <Bar value={Number(row.total_spent)} max={maxSpend} />
                <span className="chart-val">{money(row.total_spent)}</span>
              </div>
            ))}
          </div>

          <h3>Department revenue by quarter</h3>
          <div className="chart">
            {(data.revenue || []).map((row) => (
              <div className="chart-row" key={`${row.quarter}-${row.department}`}>
                <span className="chart-label">
                  {row.quarter} · {row.department}
                </span>
                <Bar
                  value={Number(row.amount)}
                  max={maxRev}
                  color={row.quarter === "2026-Q3" && row.department === "Sales" ? "#f59e0b" : "#3b82f6"}
                />
                <span className="chart-val">{money(row.amount)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {section === "customers" && (
        <>
          <input
            className="filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter customers…"
          />
          <Table
            columns={[
              { key: "customer_id", label: "ID" },
              { key: "name", label: "Name" },
              { key: "email", label: "Email" },
              { key: "signup_date", label: "Signed up" },
            ]}
            rows={customers}
          />
        </>
      )}

      {section === "orders" && (
        <>
          <input
            className="filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter orders by name, status, amount…"
          />
          <Table
            columns={[
              { key: "order_id", label: "ID" },
              { key: "customer_name", label: "Customer" },
              { key: "order_date", label: "Date" },
              { key: "amount", label: "Amount", render: (v) => money(v) },
              { key: "status", label: "Status" },
            ]}
            rows={orders}
          />
        </>
      )}

      {section === "revenue" && (
        <Table
          columns={[
            { key: "quarter", label: "Quarter" },
            { key: "department", label: "Department" },
            { key: "amount", label: "Amount", render: (v) => money(v) },
          ]}
          rows={data.revenue}
        />
      )}

      {section === "policies" && (
        <div className="policy-list">
          {Object.entries(policyGroups).map(([name, chunks]) => (
            <article className="policy-card" key={name}>
              <h3>{name}</h3>
              {chunks.map((c) => (
                <div key={c.doc_id} className="policy-chunk">
                  <div className="muted">chunk {c.chunk_index}</div>
                  <pre>{c.chunk_text}</pre>
                </div>
              ))}
            </article>
          ))}
        </div>
      )}

      {section === "log" && (
        <Table
          columns={[
            { key: "created_at", label: "When" },
            { key: "routed_mode", label: "Mode" },
            { key: "question", label: "Question" },
            {
              key: "confidence",
              label: "Conf",
              render: (v) => (v == null ? "" : Number(v).toFixed(2)),
            },
            { key: "latency_ms", label: "ms" },
          ]}
          rows={data.query_log}
        />
      )}
    </div>
  );
}

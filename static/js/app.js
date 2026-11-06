/**
 * Enterprise IT Support Agentic RAG Copilot — Frontend Application
 */

// ── State ─────────────────────────────────────────────────────────────────────
let currentSessionId = localStorage.getItem("rag_session_id");
if (!currentSessionId) {
  currentSessionId = "session_" + Math.random().toString(36).substring(2, 11);
  localStorage.setItem("rag_session_id", currentSessionId);
}

// ── DOM Elements ──────────────────────────────────────────────────────────────
const chat = document.getElementById("chat");
const form = document.getElementById("chatForm");
const question = document.getElementById("question");
const trace = document.getElementById("trace");
const sourceUsed = document.getElementById("sourceUsed");
const latencyDisplay = document.getElementById("latencyDisplay");
const pageTitle = document.getElementById("pageTitle");

// ── Tab Navigation ────────────────────────────────────────────────────────────
const navButtons = document.querySelectorAll(".nav-btn");
const tabContents = document.querySelectorAll(".tab-content");

const tabTitles = {
  "tab-overview": "System Overview & Architecture",
  "tab-chat": "AI Support Chat & Live Trace",
  "tab-kb": "Knowledge Base & Ingestion Registry",
  "tab-tickets": "IT Support Tickets",
  "tab-approvals": "Pending HITL Approvals",
  "tab-eval": "Evaluation & Benchmark Dashboard",
  "tab-health": "System Diagnostics & Telemetry",
};

function switchTab(tabId) {
  navButtons.forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  tabContents.forEach(tab => {
    tab.classList.toggle("active", tab.id === tabId);
  });
  if (pageTitle && tabTitles[tabId]) {
    pageTitle.textContent = tabTitles[tabId];
  }

  // Load dynamic data on tab switch
  if (tabId === "tab-kb") loadDocuments();
  if (tabId === "tab-tickets") loadTickets();
  if (tabId === "tab-approvals") loadApprovals();
  if (tabId === "tab-eval") loadMetrics();
  if (tabId === "tab-health") loadHealth();
}

navButtons.forEach(btn => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

function switchAndAsk(text) {
  switchTab("tab-chat");
  question.value = text;
  askAgent(text);
}

// ── HTML Escaping ─────────────────────────────────────────────────────────────
function escapeHtml(s = "") {
  return String(s).replace(/[&<>'"]/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  }[c]));
}

function formatText(s = "") {
  return escapeHtml(s).replace(/\n/g, "<br>");
}

// ── Chat Rendering ────────────────────────────────────────────────────────────
function addMessage(role, text, source = "", citations = [], verification = "") {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;

  let citeHtml = "";
  if (citations && citations.length > 0) {
    const list = citations
      .map(c => c.url
        ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">&bull; ${escapeHtml(c.title)}</a>`
        : `<span>&bull; ${escapeHtml(c.title)}</span>`
      )
      .join("<br>");
    citeHtml = `<div class="citations"><strong>Verified Sources:</strong><br>${list}</div>`;
  }

  let verifyBadge = "";
  if (verification === "grounded") {
    verifyBadge = `<span style="display:inline-block; margin-left:8px; font-size:10px; color:#4ade80; border:1px solid #22c55e; border-radius:4px; padding:1px 6px;">GROUNDED</span>`;
  }

  wrap.innerHTML = `
    <div class="avatar">${role === "assistant" ? "AI" : "YOU"}</div>
    <div class="bubble">
      ${formatText(text)}
      ${source ? `<div class="answer-source">Source: ${escapeHtml(source)} ${verifyBadge}</div>` : ""}
      ${citeHtml}
    </div>
  `;
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
}

function renderTrace(items = []) {
  if (!items || items.length === 0) {
    trace.innerHTML = '<div class="empty">No execution trace.</div>';
    return;
  }
  trace.innerHTML = items
    .map(x => `<div class="trace-item">${escapeHtml(x)}</div>`)
    .join("");
}

// ── Chat Request ──────────────────────────────────────────────────────────────
async function askAgent(q) {
  addMessage("user", q);
  question.value = "";
  renderTrace(["Initializing LangGraph pipeline...", "Preprocessing query..."]);
  sourceUsed.textContent = "Processing...";
  latencyDisplay.textContent = "...";

  const btn = form.querySelector("button");
  btn.disabled = true;
  const start = performance.now();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: q,
        session_id: currentSessionId,
      }),
    });
    const data = await res.json();
    const duration = Math.round(performance.now() - start);

    if (!res.ok) throw new Error(data.detail || "Request failed");

    addMessage(
      "assistant",
      data.answer,
      data.source_used,
      data.citations || [],
      data.verification_grade || ""
    );
    renderTrace(data.trace || []);
    sourceUsed.textContent = (data.source_used || "complete").toUpperCase();
    latencyDisplay.textContent = `${duration} ms`;

    // Refresh pending approvals if ticket created
    checkPendingApprovalsCount();
  } catch (e) {
    addMessage("assistant", `Error: ${e.message}`);
    renderTrace(["Workflow halted with error."]);
    sourceUsed.textContent = "ERROR";
    latencyDisplay.textContent = "—";
  } finally {
    btn.disabled = false;
  }
}

form.addEventListener("submit", e => {
  e.preventDefault();
  const q = question.value.trim();
  if (q) askAgent(q);
});

document.querySelectorAll("#tab-chat .example").forEach(b => {
  b.addEventListener("click", () => askAgent(b.textContent.trim()));
});

// ── Knowledge Base Ingestion ──────────────────────────────────────────────────
async function loadDocuments() {
  const tbody = document.getElementById("documentsTableBody");
  tbody.innerHTML = '<tr><td colspan="7" class="empty" style="text-align: center; padding: 20px;">Fetching documents...</td></tr>';
  try {
    const res = await fetch("/api/documents");
    const data = await res.json();
    if (!data.documents || data.documents.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty" style="text-align: center; padding: 20px;">No documents in registry. Sample documents are stored in Pinecone namespace "company-kb".</td></tr>';
      return;
    }
    tbody.innerHTML = data.documents.map(d => `
      <tr>
        <td><code>${escapeHtml(d.document_id)}</code></td>
        <td><strong>${escapeHtml(d.filename)}</strong></td>
        <td><span class="badge badge-p3">${escapeHtml(d.file_type).toUpperCase()}</span></td>
        <td>${d.chunk_count}</td>
        <td><code style="font-size:11px;">${escapeHtml(d.content_hash.substring(0, 12))}...</code></td>
        <td>${new Date(d.uploaded_at).toLocaleString()}</td>
        <td><span class="badge badge-open">${escapeHtml(d.status)}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty" style="color:var(--danger); text-align: center;">Failed to load documents: ${err.message}</td></tr>`;
  }
}

function openUploadModal() {
  document.getElementById("uploadModal").classList.remove("hidden");
}
function closeUploadModal() {
  document.getElementById("uploadModal").classList.add("hidden");
}
document.getElementById("openUpload").onclick = openUploadModal;

document.getElementById("uploadBtn").onclick = async () => {
  const file = document.getElementById("fileInput").files[0];
  const key = document.getElementById("adminKey").value;
  const status = document.getElementById("uploadStatus");

  if (!file) {
    status.textContent = "Please select a file first.";
    return;
  }
  status.textContent = "Processing and indexing vectors...";
  const fd = new FormData();
  fd.append("file", file);

  try {
    const r = await fetch("/api/ingest", {
      method: "POST",
      headers: { "X-Admin-Key": key },
      body: fd,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Upload failed");
    status.style.color = "var(--primary)";
    status.textContent = `Indexed ${d.file}: ${d.chunks} chunks created in Pinecone!`;
    loadDocuments();
    setTimeout(closeUploadModal, 1500);
  } catch (e) {
    status.style.color = "var(--danger)";
    status.textContent = `Error: ${e.message}`;
  }
};

// ── Tickets Management ────────────────────────────────────────────────────────
async function loadTickets() {
  const tbody = document.getElementById("ticketsTableBody");
  tbody.innerHTML = '<tr><td colspan="7" class="empty" style="text-align: center; padding: 20px;">Fetching tickets...</td></tr>';
  try {
    const res = await fetch("/api/tickets");
    const data = await res.json();
    if (!data.tickets || data.tickets.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty" style="text-align: center; padding: 20px;">No support tickets created yet. Use the chat or click "+ Create Ticket".</td></tr>';
      return;
    }

    tbody.innerHTML = data.tickets.map(t => {
      const pClass = t.priority === "P1" ? "badge-p1" : (t.priority === "P2" ? "badge-p2" : (t.priority === "P3" ? "badge-p3" : "badge-p4"));
      const sClass = t.status === "OPEN" ? "badge-open" : (t.status === "PENDING_APPROVAL" ? "badge-pending" : (t.status === "ESCALATED" ? "badge-escalated" : "badge-p4"));
      return `
        <tr>
          <td><code>${escapeHtml(t.ticket_id)}</code></td>
          <td><strong>${escapeHtml(t.category)}</strong></td>
          <td><span class="badge ${pClass}">${escapeHtml(t.priority)}</span></td>
          <td><span class="badge ${sClass}">${escapeHtml(t.status)}</span></td>
          <td style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(t.description)}</td>
          <td>${new Date(t.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</td>
          <td>
            ${t.status === "OPEN" ? `<button class="btn-secondary" style="font-size:11px; padding:4px 8px;" onclick="escalateTicketAction('${t.ticket_id}')">Escalate</button>` : '—'}
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty" style="color:var(--danger); text-align: center;">Failed to load tickets: ${err.message}</td></tr>`;
  }
}

async function escalateTicketAction(ticketId) {
  try {
    const res = await fetch(`/api/tickets/${ticketId}/escalate`, { method: "POST" });
    if (!res.ok) throw new Error("Escalation failed");
    loadTickets();
  } catch (e) {
    alert(e.message);
  }
}

function openTicketModal() {
  document.getElementById("ticketModal").classList.remove("hidden");
}
function closeTicketModal() {
  document.getElementById("ticketModal").classList.add("hidden");
}

document.getElementById("submitTicketBtn").onclick = async () => {
  const cat = document.getElementById("ticketCategory").value.trim();
  const pri = document.getElementById("ticketPriority").value;
  const desc = document.getElementById("ticketDescription").value.trim();
  const statusEl = document.getElementById("ticketStatus");

  if (!cat || !desc) {
    statusEl.textContent = "Please fill in all fields.";
    return;
  }

  statusEl.textContent = "Creating ticket...";
  try {
    const res = await fetch("/api/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: "employee@novaretail.internal",
        category: cat,
        priority: pri,
        description: desc,
      }),
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || "Creation failed");
    statusEl.style.color = "var(--primary)";
    statusEl.textContent = `Ticket ${d.ticket.ticket_id} created (${d.ticket.status})!`;
    loadTickets();
    checkPendingApprovalsCount();
    setTimeout(closeTicketModal, 1200);
  } catch (e) {
    statusEl.style.color = "var(--danger)";
    statusEl.textContent = `Error: ${e.message}`;
  }
};

// ── Pending Approvals (HITL) ──────────────────────────────────────────────────
async function loadApprovals() {
  const tbody = document.getElementById("approvalsTableBody");
  tbody.innerHTML = '<tr><td colspan="6" class="empty" style="text-align: center; padding: 20px;">Checking pending approvals...</td></tr>';
  try {
    const res = await fetch("/api/approvals");
    const data = await res.json();
    updateApprovalsBadge(data.total);

    if (!data.approvals || data.approvals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty" style="text-align: center; padding: 20px;">No pending approvals waiting for review.</td></tr>';
      return;
    }

    tbody.innerHTML = data.approvals.map(a => `
      <tr>
        <td><code>${escapeHtml(a.approval_id)}</code></td>
        <td><code>${escapeHtml(a.ticket_id)}</code></td>
        <td><span class="badge badge-p1">${escapeHtml(a.priority)}</span></td>
        <td>${escapeHtml(a.details)}</td>
        <td>${new Date(a.requested_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</td>
        <td>
          <button class="btn-approve" onclick="decideApprovalAction('${a.approval_id}', 'APPROVED')">Approve</button>
          <button class="btn-danger" style="margin-left:6px;" onclick="decideApprovalAction('${a.approval_id}', 'REJECTED')">Reject</button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty" style="color:var(--danger); text-align: center;">Failed to load approvals: ${err.message}</td></tr>`;
  }
}

async function decideApprovalAction(approvalId, decision) {
  try {
    const res = await fetch(`/api/approvals/${approvalId}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, decided_by: "IT Security Lead" }),
    });
    if (!res.ok) throw new Error("Decision submission failed");
    loadApprovals();
  } catch (e) {
    alert(e.message);
  }
}

async function checkPendingApprovalsCount() {
  try {
    const res = await fetch("/api/approvals");
    const data = await res.json();
    updateApprovalsBadge(data.total);
  } catch (e) {}
}

function updateApprovalsBadge(count) {
  const badge = document.getElementById("approvalsBadge");
  if (!badge) return;
  if (count > 0) {
    badge.textContent = count;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

// ── Evaluation & Metrics Dashboard ────────────────────────────────────────────
async function loadMetrics() {
  try {
    const res = await fetch("/api/metrics");
    const data = await res.json();

    // Benchmarks
    const bench = data.benchmark_evaluation || {};
    const r = bench.retrieval || {};
    const g = bench.generation || {};

    if (r["recall@4"] !== undefined) {
      document.getElementById("evalRecall").textContent = `${(r["recall@4"] * 100).toFixed(1)}%`;
      document.getElementById("evalPrecision").textContent = `${(r["precision@4"] * 100).toFixed(1)}%`;
      document.getElementById("evalMRR").textContent = r["mrr"].toFixed(3);
      document.getElementById("evalNDCG").textContent = r["ndcg@4"].toFixed(3);
      document.getElementById("evalFacts").textContent = `${(g["fact_coverage"] * 100).toFixed(1)}%`;
      document.getElementById("evalFaith").textContent = `${(g["faithfulness"] * 100).toFixed(1)}%`;
    } else {
      document.getElementById("evalRecall").textContent = "Not evaluated";
    }

    // Telemetry Latency
    const tel = data.telemetry || {};
    const lat = tel.latency_summary_ms || {};
    document.getElementById("telemetryAvg").textContent = `${lat.avg || 0} ms`;
    document.getElementById("telemetryP50").textContent = `${lat.p50 || 0} ms`;
    document.getElementById("telemetryP95").textContent = `${lat.p95 || 0} ms`;
    document.getElementById("telemetryP99").textContent = `${lat.p99 || 0} ms`;
  } catch (e) {
    console.error("Failed to load metrics:", e);
  }
}

// ── Health Diagnostics ────────────────────────────────────────────────────────
async function loadHealth() {
  const telEl = document.getElementById("healthTelemetry");
  telEl.textContent = "Querying live metrics...";
  try {
    const [hRes, mRes] = await Promise.all([fetch("/api/health"), fetch("/api/metrics")]);
    const hData = await hRes.json();
    const mData = await mRes.json();

    document.getElementById("healthModel").textContent = hData.model || "Groq";
    document.getElementById("healthEmbed").textContent = hData.embedding || "all-MiniLM-L6-v2";

    const tel = mData.telemetry || {};
    const routes = tel.routing_distribution || {};
    const kb = tel.knowledge_base || {};

    telEl.innerHTML = `
      <div><strong>Total Audit Queries Recorded:</strong> ${tel.total_requests || 0}</div>
      <div><strong>Registered Documents:</strong> ${kb.indexed_documents || 0} (${kb.indexed_chunks || 0} chunks)</div>
      <div><strong>Routing Breakdown:</strong></div>
      <ul style="margin:4px 0 0 16px; padding:0;">
        ${Object.entries(routes).map(([k, v]) => `<li><code>${k}</code>: ${v} queries</li>`).join("") || "<li>No requests logged yet</li>"}
      </ul>
      <div style="margin-top:8px;"><strong>Environment:</strong> <code>${hData.env}</code></div>
    `;
  } catch (e) {
    telEl.innerHTML = `<span style="color:var(--danger)">Diagnostics check failed: ${e.message}</span>`;
  }
}

// Initial checks on page load
checkPendingApprovalsCount();

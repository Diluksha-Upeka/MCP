"use client";

import { useEffect, useState } from "react";
import { useSession, signIn, signOut } from "next-auth/react";

type Approval = {
  id: number;
  tool_name: string;
  request: Record<string, unknown>;
  status: string;
  requested_by: string;
  reason: string;
  created_at: string;
};

type ChatMessage = {
  role: "user" | "agent";
  content: string;
};

export default function Home() {
  const { data: session, status: authStatus } = useSession();
  const isSignedIn = authStatus === "authenticated";

  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [status, setStatus] = useState("Idle");

  const loadApprovals = async () => {
    if (!isSignedIn) return;
    const resp = await fetch("/api/approvals");
    if (!resp.ok) return;
    const data = await resp.json();
    setApprovals(data);
  };

  useEffect(() => {
    if (isSignedIn) {
      loadApprovals();
      const timer = setInterval(loadApprovals, 8000);
      return () => clearInterval(timer);
    }
  }, [isSignedIn]);

  const sendQuery = async () => {
    if (!query.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setStatus("Routing...");
    const resp = await fetch("/api/mcp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ query })
    });
    const data = await resp.json();
    setMessages((prev) => [...prev, { role: "agent", content: JSON.stringify(data, null, 2) }]);
    setStatus("Idle");
    setQuery("");
    loadApprovals();
  };

  const reviewApproval = async (id: number, statusParams: "approved" | "rejected") => {
    if (!isSignedIn) return;
    await fetch(`/api/approvals/${id}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ status: statusParams })
    });
    loadApprovals();
  };

  return (
    <div>
      <header className="header">
        <div>
          <div className="brand">MCP Ops Console</div>
          <div className="muted">Secure agent workflows with Google OAuth</div>
        </div>
        <div>
          {isSignedIn ? (
            <button className="action-button reject" onClick={() => signOut()}>Sign Out ({session?.user?.email})</button>
          ) : (
            <button className="action-button" onClick={() => signIn("google")}>Sign in with Google</button>
          )}
        </div>
      </header>

      <main>
        <section className="panel">
          <h2>Operational Snapshot</h2>
          <div className="sidebar-list">
            <div className="stat">Status: {status}</div>
            <div className="stat">Pending approvals: {approvals.length}</div>
            <div className="stat">Security posture: NextAuth OAuth</div>
            <div className="stat">Hybrid routing: vector + graph</div>
          </div>
          <div style={{ marginTop: 20 }} className="timeline">
            <div className="timeline-item">Tool calls are audited with full request/response.</div>
            <div className="timeline-item">Sensitive actions pause the agent until approval.</div>
            <div className="timeline-item">Google OAuth manages human identity safely.</div>
          </div>
        </section>

        <section className="panel">
          <div className="tag">Agent Chat</div>
          <h2>Command Center</h2>
          <div className="chat-box">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                <strong>{msg.role === "user" ? "You" : "Agent"}</strong>
                <pre style={{ whiteSpace: "pre-wrap", margin: "8px 0 0" }}>{msg.content}</pre>
              </div>
            ))}
          </div>
          <div className="input-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about SOPs, incidents, logs, or dependencies..."
              disabled={!isSignedIn}
            />
            <button onClick={sendQuery} disabled={!isSignedIn}>Dispatch</button>
          </div>
          {!isSignedIn && <div className="muted" style={{ marginTop: 10 }}>Sign in to run queries.</div>}
        </section>

        <section className="panel">
          <div className="tag">HITL Queue</div>
          <h2>Approval Inbox</h2>
          {!isSignedIn && <div className="muted">Sign in to view approvals.</div>}
          {isSignedIn && approvals.length === 0 && <div className="muted">No pending approvals.</div>}
          {isSignedIn && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {approvals.map((approval) => (
                <div key={approval.id} className="approval-card">
                  <div><strong>{approval.tool_name}</strong> · {approval.requested_by}</div>
                  <div className="muted">{approval.reason}</div>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(approval.request, null, 2)}</pre>
                  <div className="approval-actions">
                    <button className="action-button" onClick={() => reviewApproval(approval.id, "approved")}>Approve</button>
                    <button className="action-button reject" onClick={() => reviewApproval(approval.id, "rejected")}>Reject</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

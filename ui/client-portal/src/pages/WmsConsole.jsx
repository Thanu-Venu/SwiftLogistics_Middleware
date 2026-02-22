import { useState } from "react";
import { API_BASE } from "../config";

export default function WmsConsole() {
  const [message, setMessage] = useState("ADD_PACKAGE|ORD-DEMO");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const send = async () => {
    setErr(""); setReply(""); setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/internal/wms/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await r.json();
      setReply(data.reply || "");
    } catch (e) {
      setErr(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h2 className="text-xl font-bold">WMS Console (TCP)</h2>
      <p className="mt-1 text-sm text-gray-600">UI → API Gateway → WMS TCP mock (browser direct TCP cannot)</p>

      <div className="mt-5">
        <label className="block text-sm font-medium text-gray-700">TCP Message</label>
        <input className="mt-1 w-full rounded-xl border px-3 py-2 font-mono"
          value={message} onChange={(e)=>setMessage(e.target.value)} />
      </div>

      <button
        onClick={send}
        disabled={loading}
        className="mt-4 rounded-xl bg-black text-white px-4 py-2 font-semibold disabled:opacity-50"
      >
        {loading ? "Sending..." : "Send TCP"}
      </button>

      {err && <div className="mt-4 rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">{err}</div>}

      <div className="mt-4 rounded-2xl border bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-700">WMS Reply</div>
        <div className="mt-2 font-mono text-sm">{reply || "—"}</div>
      </div>
    </div>
  );
}
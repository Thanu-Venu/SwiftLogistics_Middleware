import { useState } from "react";
import { API_BASE } from "../config";

export default function CmsConsole() {
  const [orderId, setOrderId] = useState("ORD-DEMO");
  const [clientId, setClientId] = useState("C001");
  const [resp, setResp] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const send = async () => {
    setErr(""); setResp(""); setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/internal/cms/soap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: orderId, client_id: clientId }),
      });
      const data = await r.json();
      setResp(data.response_xml || "");
    } catch (e) {
      setErr(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h2 className="text-xl font-bold">CMS Console (SOAP)</h2>
      <p className="mt-1 text-sm text-gray-600">UI → API Gateway → CMS SOAP mock</p>

      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Order ID</label>
          <input className="mt-1 w-full rounded-xl border px-3 py-2 font-mono"
            value={orderId} onChange={(e)=>setOrderId(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Client ID</label>
          <input className="mt-1 w-full rounded-xl border px-3 py-2"
            value={clientId} onChange={(e)=>setClientId(e.target.value)} />
        </div>
      </div>

      <button
        onClick={send}
        disabled={loading}
        className="mt-4 rounded-xl bg-black text-white px-4 py-2 font-semibold disabled:opacity-50"
      >
        {loading ? "Sending..." : "Send SOAP Request"}
      </button>

      {err && <div className="mt-4 rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">{err}</div>}

      <div className="mt-4 rounded-2xl border bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-700">SOAP Response (XML)</div>
        <pre className="mt-2 text-xs overflow-auto whitespace-pre-wrap">{resp || "—"}</pre>
      </div>
    </div>
  );
}
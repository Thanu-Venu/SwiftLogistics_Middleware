import { useState } from "react";
import { API_BASE } from "../config";

export default function RosConsole() {
  const [orderId, setOrderId] = useState("ORD-DEMO");
  const [resp, setResp] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const send = async () => {
    setErr(""); setResp(null); setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/internal/ros/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: orderId }),
      });
      const data = await r.json();
      setResp(data.response_json || data);
    } catch (e) {
      setErr(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h2 className="text-xl font-bold">ROS Console (REST)</h2>
      <p className="mt-1 text-sm text-gray-600">UI → API Gateway → ROS REST mock</p>

      <div className="mt-5">
        <label className="block text-sm font-medium text-gray-700">Order ID</label>
        <input className="mt-1 w-full rounded-xl border px-3 py-2 font-mono"
          value={orderId} onChange={(e)=>setOrderId(e.target.value)} />
      </div>

      <button
        onClick={send}
        disabled={loading}
        className="mt-4 rounded-xl bg-black text-white px-4 py-2 font-semibold disabled:opacity-50"
      >
        {loading ? "Calling..." : "Optimize Route"}
      </button>

      {err && <div className="mt-4 rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">{err}</div>}

      <div className="mt-4 rounded-2xl border bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-700">REST Response (JSON)</div>
        <pre className="mt-2 text-xs overflow-auto whitespace-pre-wrap">
          {resp ? JSON.stringify(resp, null, 2) : "—"}
        </pre>
      </div>
    </div>
  );
}
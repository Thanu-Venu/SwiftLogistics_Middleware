import { useEffect, useState } from "react";
import { API_BASE } from "../config";

export default function RosConsole() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      const r = await fetch(`${API_BASE}/internal/ros/last`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j);
    } catch (e) {
      setErr(e.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 1500); // poll every 1.5s
    return () => clearInterval(t);
  }, []);

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h2 className="text-xl font-bold">ROS Console (REST)</h2>
      <p className="mt-1 text-sm text-gray-600">
        Worker → API Gateway → ROS REST mock (auto)
      </p>

      {loading && <div className="mt-4 text-sm text-gray-500">Loading…</div>}
      {err && (
        <div className="mt-4 rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
          {err}
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <Info label="Last Seen" value={data?.seen_at || "—"} />
        <Info label="Order ID" value={data?.order_id || "—"} mono />
        <Info label="Status" value={data?.response_json?.status || "—"} />
      </div>

      <div className="mt-4 rounded-2xl border bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-700">REST Request (JSON)</div>
        <pre className="mt-2 text-xs overflow-auto whitespace-pre-wrap">
          {data?.request_json ? JSON.stringify(data.request_json, null, 2) : "—"}
        </pre>
      </div>

      <div className="mt-4 rounded-2xl border bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-700">REST Response (JSON)</div>
        <pre className="mt-2 text-xs overflow-auto whitespace-pre-wrap">
          {data?.response_json ? JSON.stringify(data.response_json, null, 2) : "—"}
        </pre>
      </div>

      <button
        onClick={load}
        className="mt-4 rounded-xl bg-black text-white px-4 py-2 font-semibold"
      >
        Refresh
      </button>
    </div>
  );
}

function Info({ label, value, mono }) {
  return (
    <div className="rounded-xl border p-3">
      <div className="text-xs font-semibold text-gray-600">{label}</div>
      <div className={`mt-1 text-sm ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}
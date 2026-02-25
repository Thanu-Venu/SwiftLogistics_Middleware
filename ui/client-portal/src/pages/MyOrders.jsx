import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";

function fmtTs(ts) {
  if (!ts) return "-";
  const n = Number(ts);
  if (!Number.isFinite(n)) return "-";

  // 13 digits => ms, 10 digits => sec
  const d = n > 1e12 ? new Date(n) : new Date(n * 1000);
  if (isNaN(d.getTime())) return "-";
  return d.toLocaleString();
}

export default function MyOrders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("ALL");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const res = await api("/orders/my");
      setOrders(res.orders || []);
    } catch (e) {
      setErr(e.message || "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const qq = q.trim().toLowerCase();
    return orders.filter((o) => {
      const okStatus = status === "ALL" ? true : o.status === status;
      const okQ =
        !qq ||
        (o.id || "").toLowerCase().includes(qq) ||
        JSON.stringify(o.payload || {}).toLowerCase().includes(qq);
      return okStatus && okQ;
    });
  }, [orders, q, status]);

  const statuses = useMemo(() => {
    const set = new Set(orders.map((o) => o.status).filter(Boolean));
    return ["ALL", ...Array.from(set)];
  }, [orders]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">My Orders</h1>
          <p className="text-sm text-gray-600">View your recent orders & statuses</p>
        </div>

        <button
          className="px-3 py-2 rounded-lg bg-black text-white"
          onClick={load}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <input
          className="w-full md:flex-1 border rounded-lg px-3 py-2"
          placeholder="Search by order id / payload..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />

        <select
          className="w-full md:w-56 border rounded-lg px-3 py-2"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {statuses.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {err && (
        <div className="border border-red-200 bg-red-50 text-red-700 rounded-lg p-3">
          {err}
        </div>
      )}

      {loading ? (
        <div className="p-6 text-gray-600">Loading orders...</div>
      ) : filtered.length === 0 ? (
        <div className="p-6 border rounded-xl bg-white">
          <div className="text-gray-700 font-medium">No orders found</div>
          <div className="text-gray-500 text-sm mt-1">
            Try changing filters or place a new order.
          </div>
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map((o) => (
            <div key={o.id} className="border rounded-xl bg-white p-4">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                <div className="font-mono text-sm">{o.id}</div>

                <div className="flex items-center gap-3">
                  <span className="text-xs px-2 py-1 rounded-full bg-gray-100">
                    {fmtTs(o.created_at)}
                  </span>
                  <span className="text-sm font-semibold">{o.status}</span>
                </div>
              </div>

              <details className="mt-3">
                <summary className="cursor-pointer text-sm text-gray-700">
                  View payload
                </summary>
                <pre className="mt-2 text-xs bg-gray-50 border rounded-lg p-3 overflow-auto">
                  {JSON.stringify(o.payload || {}, null, 2)}
                </pre>
              </details>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
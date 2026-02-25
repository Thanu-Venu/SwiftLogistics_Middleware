import { useEffect, useState } from "react";
import { api } from "../api/client";

const StatCard = ({ label, value }) => (
  <div className="rounded-2xl border bg-white p-4 shadow-sm">
    <div className="text-xs font-semibold text-gray-500">{label}</div>
    <div className="mt-1 text-2xl font-extrabold">{value}</div>
  </div>
);

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [orders, setOrders] = useState([]);
  const [status, setStatus] = useState("");
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      const s = await api("/admin/stats");
      setStats(s);
      const list = await api(status ? `/admin/orders?status=${encodeURIComponent(status)}` : "/admin/orders");
      setOrders(list);
    } catch (e) {
      setErr(e.message || "Error");
    }
  }

  useEffect(() => { load(); }, [status]); // eslint-disable-line

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Admin Portal</h1>
            <p className="mt-1 text-sm text-gray-600">Monitor orders, pipeline health, and events.</p>
          </div>
          <button
            onClick={load}
            className="rounded-xl bg-black px-4 py-2 text-white font-semibold hover:opacity-90"
          >
            Refresh
          </button>
        </div>

        {err && <div className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}

        <div className="mt-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Total" value={stats?.total ?? "-"} />
          <StatCard label="New" value={stats?.new ?? "-"} />
          <StatCard label="Ready" value={stats?.ready_for_driver ?? "-"} />
          <StatCard label="Delivered" value={stats?.delivered ?? "-"} />
          <StatCard label="Failed" value={stats?.failed ?? "-"} />
          <StatCard label="DLQ" value={stats?.dlq ?? "-"} />
        </div>

        <div className="mt-6 rounded-2xl border bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-lg font-bold">Orders</div>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-xl border px-3 py-2 text-sm"
            >
              <option value="">All</option>
              <option value="NEW">NEW</option>
              <option value="PROCESSING">PROCESSING</option>
              <option value="READY_FOR_DRIVER">READY_FOR_DRIVER</option>
              <option value="DELIVERED">DELIVERED</option>
              <option value="FAILED">FAILED</option>
              <option value="DLQ">DLQ</option>
            </select>
          </div>

          <div className="mt-4 overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-gray-500">
                <tr className="border-b">
                  <th className="py-2 pr-4">Order ID</th>
                  <th className="py-2 pr-4">Client</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-mono">{o.id}</td>
                    <td className="py-2 pr-4 font-mono">{o.client_id}</td>
                    <td className="py-2 pr-4">
                      <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold">
                        {o.status}
                      </span>
                    </td>
                    <td className="py-2 pr-4">{String(o.created_at)}</td>
                  </tr>
                ))}
                {orders.length === 0 && (
                  <tr><td className="py-3 text-gray-500" colSpan={4}>No orders</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-gray-500">
            Tip: Click an order in your future version to open <span className="font-mono">/admin/events/&lt;order_id&gt;</span>.
          </p>
        </div>
      </div>
    </div>
  );
}
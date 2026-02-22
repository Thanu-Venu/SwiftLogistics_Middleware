import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      setErr("");
      try {
        const res = await api("/orders/my");
        setOrders(res.orders || []);
      } catch (e) {
        setErr(e.message || "Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const stats = useMemo(() => {
    const total = orders.length;
    const byStatus = orders.reduce((acc, o) => {
      const s = o.status || "UNKNOWN";
      acc[s] = (acc[s] || 0) + 1;
      return acc;
    }, {});
    const top = Object.entries(byStatus)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
    return { total, top };
  }, [orders]);

  function handleLogout() {
    logout();
    nav("/login", { replace: true });
  }

  return (
    <div className="space-y-5">
      <div className="bg-white border rounded-2xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Dashboard</h1>
            <p className="text-gray-600 mt-1 text-sm">
              Welcome{user?.email ? `, ${user.email}` : ""} 👋
            </p>
          </div>

          <button
            onClick={handleLogout}
            className="px-3 py-2 rounded-lg border bg-white hover:bg-gray-50"
          >
            Logout
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="border rounded-xl p-4 bg-gray-50">
            <div className="text-xs text-gray-500">Client ID</div>
            <div className="font-semibold">{user?.client_id || "-"}</div>
          </div>

          <div className="border rounded-xl p-4 bg-gray-50">
            <div className="text-xs text-gray-500">Role</div>
            <div className="font-semibold">{user?.role || "-"}</div>
          </div>

          <div className="border rounded-xl p-4 bg-gray-50">
            <div className="text-xs text-gray-500">Total Orders</div>
            <div className="font-semibold">{loading ? "..." : stats.total}</div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Link className="px-3 py-2 rounded-lg bg-black text-white" to="/">
            Client Portal
          </Link>
          <Link className="px-3 py-2 rounded-lg border bg-white" to="/my-orders">
            My Orders
          </Link>
          <Link className="px-3 py-2 rounded-lg border bg-white" to="/cms">
            CMS
          </Link>
          <Link className="px-3 py-2 rounded-lg border bg-white" to="/ros">
            ROS
          </Link>
          <Link className="px-3 py-2 rounded-lg border bg-white" to="/wms">
            WMS
          </Link>
        </div>
      </div>

      {err && (
        <div className="border border-red-200 bg-red-50 text-red-700 rounded-lg p-3">
          {err}
        </div>
      )}

      <div className="bg-white border rounded-2xl p-5">
        <h2 className="text-lg font-semibold">Order Status Summary</h2>
        <p className="text-sm text-gray-600 mt-1">
          Top statuses from your recent orders
        </p>

        {loading ? (
          <div className="p-4 text-gray-600">Loading summary...</div>
        ) : orders.length === 0 ? (
          <div className="p-4 text-gray-600">No orders yet.</div>
        ) : (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3">
            {stats.top.map(([s, count]) => (
              <div key={s} className="border rounded-xl p-4 bg-gray-50">
                <div className="text-xs text-gray-500">{s}</div>
                <div className="text-2xl font-semibold">{count}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
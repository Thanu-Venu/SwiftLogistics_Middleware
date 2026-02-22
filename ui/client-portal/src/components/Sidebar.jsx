import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const Item = ({ to, label }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      [
        "block rounded-xl px-3 py-2 text-sm font-semibold",
        isActive ? "bg-black text-white" : "text-gray-700 hover:bg-gray-100",
      ].join(" ")
    }
  >
    {label}
  </NavLink>
);

export default function Sidebar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const doLogout = () => {
    logout();
    nav("/login", { replace: true });
  };

  return (
    <aside className="w-64 shrink-0 border-r bg-white p-4">
      <div className="text-lg font-extrabold">SwiftLogistics</div>
      <div className="mt-1 text-xs text-gray-500">Middleware Dashboard</div>

      {/* user info */}
      <div className="mt-4 rounded-xl border bg-gray-50 p-3">
        <div className="text-xs text-gray-500">Logged in</div>
        <div className="text-sm font-semibold text-gray-900 truncate">
          {user?.email || "-"}
        </div>
        <div className="mt-1 text-xs text-gray-600 font-mono">
          {user?.client_id ? `Client: ${user.client_id}` : "Client: -"}
        </div>
      </div>

      {/* main nav */}
      <nav className="mt-6 space-y-2">
        <Item to="/dashboard" label="Dashboard" />
        <Item to="/" label="Client Portal" />
        <Item to="/my-orders" label="My Orders" />

        <div className="pt-2">
          <div className="px-3 text-xs font-semibold text-gray-500">Integrations</div>
          <div className="mt-2 space-y-2">
            <Item to="/cms" label="CMS Console (SOAP)" />
            <Item to="/ros" label="ROS Console (REST)" />
            <Item to="/wms" label="WMS Console (TCP)" />
          </div>
        </div>
      </nav>

      {/* logout */}
      <div className="mt-6">
        <button
          onClick={doLogout}
          className="w-full rounded-xl border px-3 py-2 text-sm font-semibold hover:bg-gray-50"
        >
          Logout
        </button>
      </div>

      <div className="mt-6 text-xs text-gray-500">
        Phase 1: JWT protected routes ✅
      </div>
    </aside>
  );
}
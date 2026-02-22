import { NavLink } from "react-router-dom";

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
  return (
    <aside className="w-64 shrink-0 border-r bg-white p-4">
      <div className="text-lg font-extrabold">SwiftLogistics</div>
      <div className="mt-1 text-xs text-gray-500">Middleware Dashboard</div>

      <nav className="mt-6 space-y-2">
        <Item to="/" label="Client Portal" />
        <Item to="/cms" label="CMS Console (SOAP)" />
        <Item to="/ros" label="ROS Console (REST)" />
        <Item to="/wms" label="WMS Console (TCP)" />
      </nav>

      <div className="mt-10 text-xs text-gray-500">
        Tip: Client portal login add pannrom next.
      </div>
    </aside>
  );
}
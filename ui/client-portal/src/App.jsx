import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";

import ClientPortal from "./pages/ClientPortal";
import CmsConsole from "./pages/CmsConsole";
import RosConsole from "./pages/RosConsole";
import WmsConsole from "./pages/WmsConsole";

import Dashboard from "./pages/Dashboard";
import MyOrders from "./pages/MyOrders";

import Login from "./pages/Login";
import Register from "./pages/Register";

import RequireAuth from "./auth/RequireAuth";

import Driver from "./pages/Driver";
import Admin from "./pages/Admin";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ✅ Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/driver" element={<Driver />} />
        <Route path="/admin" element={<Admin />} />

        {/* ✅ Protected routes */}
        <Route element={<RequireAuth />}>
          <Route
            path="/*"
            element={
              <div className="min-h-screen bg-gray-50 flex">
                <Sidebar />
                <main className="flex-1 p-6">
                  <div className="max-w-5xl mx-auto">
                    <Routes>
                      <Route path="/" element={<ClientPortal />} />
                      <Route path="/dashboard" element={<Dashboard />} />
                      <Route path="/my-orders" element={<MyOrders />} />

                      <Route path="/cms" element={<CmsConsole />} />
                      <Route path="/ros" element={<RosConsole />} />
                      <Route path="/wms" element={<WmsConsole />} />
                    </Routes>
                  </div>
                </main>
              </div>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
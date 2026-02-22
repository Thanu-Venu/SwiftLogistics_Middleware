import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";

import ClientPortal from "./pages/ClientPortal";
import CmsConsole from "./pages/CmsConsole";
import RosConsole from "./pages/RosConsole";
import WmsConsole from "./pages/WmsConsole";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 flex">
        <Sidebar />
        <main className="flex-1 p-6">
          <div className="max-w-5xl mx-auto">
            <Routes>
              <Route path="/" element={<ClientPortal />} />
              <Route path="/cms" element={<CmsConsole />} />
              <Route path="/ros" element={<RosConsole />} />
              <Route path="/wms" element={<WmsConsole />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}
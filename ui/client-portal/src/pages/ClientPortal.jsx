import { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from "../config";

const badgeClass = (s) => {
  if (!s) return "bg-gray-100 text-gray-700";
  if (s.includes("ERROR") || s.includes("NACK")) return "bg-red-100 text-red-700";
  if (s.includes("CALLING") || s === "PROCESSING") return "bg-yellow-100 text-yellow-800";
  if (s.endsWith("_OK") || s === "READY_FOR_DRIVER") return "bg-green-100 text-green-700";
  return "bg-blue-100 text-blue-700";
};

export default function ClientPortal() {
  const [clientId, setClientId] = useState("C001");
  const [destination, setDestination] = useState("Colombo");
  const [sku, setSku] = useState("A1");
  const [qty, setQty] = useState(2);

  const [orderId, setOrderId] = useState("");
  const [currentStatus, setCurrentStatus] = useState("");
  const [statusLog, setStatusLog] = useState([]);

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const wsRef = useRef(null);

  const wsUrl = useMemo(() => {
    if (!orderId) return "";
    const base = API_BASE.replace(/^http/, "ws");
    return `${base}/ws/orders/${orderId}`;
  }, [orderId]);

  const addStatus = (s) => {
    setCurrentStatus(s);
    setStatusLog((prev) => {
      if (prev.length > 0 && prev[prev.length - 1] === s) return prev;
      return [...prev, s];
    });
  };

  const disconnectWs = () => {
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {}
      wsRef.current = null;
    }
  };

  const connectWs = () => {
    if (!wsUrl) return;
    disconnectWs();

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // keep-alive ping so server doesn't disconnect waiting for receive_text
      try {
        ws.send("ping");
      } catch {}
    };

    ws.onmessage = (evt) => {
      const s = (evt.data || "").toString();
      if (s) addStatus(s);
    };

    ws.onerror = () => {};
    ws.onclose = () => {};
  };

  useEffect(() => {
    if (!orderId) return;
    connectWs();
    return () => disconnectWs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId, wsUrl]);

  const createOrder = async () => {
    setErr("");
    setLoading(true);
    setStatusLog([]);
    setCurrentStatus("");
    disconnectWs();

    try {
      const res = await fetch(`${API_BASE}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId.trim(),
          destination: destination.trim(),
          items: [{ sku: sku.trim(), qty: Number(qty) || 1 }],
        }),
      });

      if (!res.ok) {
        const t = await res.text();
        throw new Error(`Create failed: ${res.status} ${t}`);
      }

      const data = await res.json();
      setOrderId(data.order_id);
      addStatus(data.status || "PENDING");
    } catch (e) {
      setErr(e.message || "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    if (!orderId) return;
    setErr("");
    try {
      const res = await fetch(`${API_BASE}/orders/${orderId}`);
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`Fetch failed: ${res.status} ${t}`);
      }
      const data = await res.json();
      if (data?.status) addStatus(data.status);
    } catch (e) {
      setErr(e.message || "Unknown error");
    }
  };

  const clearAll = () => {
    setOrderId("");
    setCurrentStatus("");
    setStatusLog([]);
    setErr("");
    disconnectWs();
  };

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight">Client Portal</h2>
          <p className="mt-1 text-sm text-gray-600">
            Create an order and track live status updates (WebSocket) from the middleware pipeline.
          </p>
        </div>

        <div className="text-sm text-gray-600">
          <div className="font-medium text-gray-800">API</div>
          <div className="font-mono">{API_BASE}</div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Create Order */}
        <div className="rounded-2xl border bg-gray-50 p-5">
          <h3 className="text-lg font-bold">Create Order</h3>

          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Client ID</label>
              <input
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
                placeholder="C001"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Destination</label>
              <input
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
                placeholder="Colombo"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700">Item SKU</label>
                <input
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                  className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
                  placeholder="A1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Qty</label>
                <input
                  type="number"
                  min="1"
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
                />
              </div>
            </div>

            <button
              onClick={createOrder}
              disabled={loading}
              className="w-full rounded-xl bg-black text-white py-2 font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create Order"}
            </button>

            {err && (
              <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
                {err}
              </div>
            )}
          </div>
        </div>

        {/* Tracking */}
        <div className="rounded-2xl border bg-gray-50 p-5">
          <h3 className="text-lg font-bold">Tracking</h3>

          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Order ID</label>
              <input
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
                className="mt-1 w-full rounded-xl border px-3 py-2 font-mono focus:outline-none focus:ring"
                placeholder="ORD-..."
              />
              <p className="mt-2 text-xs text-gray-500">
                Creating an order will auto-fill this. You can also paste an existing order id.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <span
                className={`inline-flex w-fit items-center px-3 py-1 rounded-full text-sm font-medium ${badgeClass(
                  currentStatus
                )}`}
              >
                {currentStatus || "No status yet"}
              </span>

              {orderId && (
                <div className="text-xs text-gray-500">
                  WS: <span className="font-mono">{wsUrl}</span>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={fetchStatus}
                disabled={!orderId}
                className="rounded-xl border px-4 py-2 font-semibold hover:bg-white disabled:opacity-50"
              >
                Refresh (GET)
              </button>
              <button
                onClick={connectWs}
                disabled={!orderId}
                className="rounded-xl border px-4 py-2 font-semibold hover:bg-white disabled:opacity-50"
              >
                Reconnect WS
              </button>
              <button
                onClick={clearAll}
                className="rounded-xl border px-4 py-2 font-semibold hover:bg-white"
              >
                Clear
              </button>
            </div>

            <div className="rounded-2xl border bg-white p-4">
              <div className="text-sm font-semibold text-gray-700">Live Status Log</div>
              <div className="mt-3 space-y-2 max-h-64 overflow-auto">
                {statusLog.length === 0 ? (
                  <div className="text-sm text-gray-500">No updates yet.</div>
                ) : (
                  statusLog.map((s, idx) => (
                    <div key={`${s}-${idx}`} className="flex items-center justify-between gap-3">
                      <div className="text-sm font-mono text-gray-800">{s}</div>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass(s)}`}>
                        {idx + 1}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            <p className="text-xs text-gray-500">
              Tip: Worker is very fast. Add <span className="font-mono">time.sleep(2)</span> between worker steps to visualize.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
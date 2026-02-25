import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";

const badge = (s) => {
  if (!s) return "bg-gray-100 text-gray-700";
  if (s.includes("ERROR") || s.includes("NACK") || s === "FAILED") return "bg-red-100 text-red-700";
  if (s.includes("CALLING") || s === "PROCESSING" || s === "OUT_FOR_DELIVERY") return "bg-yellow-100 text-yellow-800";
  if (s.endsWith("_OK") || s === "READY_FOR_DRIVER" || s === "DELIVERED") return "bg-green-100 text-green-700";
  return "bg-blue-100 text-blue-700";
};

function Modal({ open, title, children, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl border">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="text-lg font-bold">{title}</div>
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-1 text-sm border hover:bg-gray-50"
          >
            Close
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

export default function Driver() {
  const [tab, setTab] = useState("manifest"); // manifest | assigned
  const [manifest, setManifest] = useState({ driver_id: "", orders: [] });
  const [orders, setOrders] = useState([]);

  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const [active, setActive] = useState(null);

  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  // Proof UI
  const [photoDataUrl, setPhotoDataUrl] = useState("");
  const [proofErr, setProofErr] = useState("");
  const canvasRef = useRef(null);
  const drawing = useRef(false);

  // Fail modal
  const [failOpen, setFailOpen] = useState(false);
  const [failReason, setFailReason] = useState("");

  async function loadAssigned() {
    setErr("");
    setLoading(true);
    try {
      const list = await api("/driver/orders");
      setOrders(list);
    } catch (e) {
      setErr(e.message || "Error");
    } finally {
      setLoading(false);
    }
  }

  async function loadManifest() {
    setErr("");
    setLoading(true);
    try {
      const data = await api("/driver/manifest/today");
      setManifest(data);
    } catch (e) {
      setErr(e.message || "Error");
    } finally {
      setLoading(false);
    }
  }

  async function refresh() {
    if (tab === "manifest") await loadManifest();
    else await loadAssigned();
  }

  useEffect(() => {
    refresh(); // eslint-disable-next-line
  }, [tab]);

  // pick list based on tab
  const list = useMemo(() => {
    const base = tab === "manifest" ? (manifest.orders || []) : orders;

    const filtered = base.filter((o) => {
      const text = `${o.id} ${o.client_id}`.toLowerCase();
      if (q.trim() && !text.includes(q.trim().toLowerCase())) return false;
      if (statusFilter !== "ALL" && o.status !== statusFilter) return false;
      return true;
    });

    return filtered;
  }, [tab, manifest, orders, q, statusFilter]);

  // auto select first item
  useEffect(() => {
    if (!active && list.length > 0) setActive(list[0]);
    // if active no longer in list, select first
    if (active && list.length > 0 && !list.find((x) => x.id === active.id)) {
      setActive(list[0]);
    }
    if (list.length === 0) setActive(null);
    // eslint-disable-next-line
  }, [list.length]);

  // ---------- Signature canvas ----------
  const clearSignature = () => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
  };

  const pointerPos = (evt, canvas) => {
    const rect = canvas.getBoundingClientRect();
    const x = (evt.clientX - rect.left) * (canvas.width / rect.width);
    const y = (evt.clientY - rect.top) * (canvas.height / rect.height);
    return { x, y };
  };

  const startDraw = (e) => {
    const c = canvasRef.current;
    if (!c) return;
    drawing.current = true;
    const ctx = c.getContext("2d");
    const p = pointerPos(e, c);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  };

  const moveDraw = (e) => {
    if (!drawing.current) return;
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    const p = pointerPos(e, c);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  };

  const endDraw = () => {
    drawing.current = false;
  };

  const onPhotoPick = (file) => {
    setProofErr("");
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setProofErr("Please choose an image file");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPhotoDataUrl(String(reader.result || ""));
    reader.readAsDataURL(file);
  };

  async function uploadProof() {
    setProofErr("");
    if (!active) return;

    try {
      // Photo optional
      if (photoDataUrl) {
        await api(`/driver/orders/${active.id}/proof`, {
          method: "POST",
          body: JSON.stringify({
            proof_type: "photo",
            data_base64: photoDataUrl,
            meta: { name: "photo" },
          }),
        });
      }

      // Signature required (you can make optional, but better UX to require)
      const c = canvasRef.current;
      if (!c) throw new Error("Signature canvas missing");
      const sig = c.toDataURL("image/png");
      // tiny check: if blank-ish, will still be small
      if (!sig || sig.length < 2000) throw new Error("Please add signature");

      await api(`/driver/orders/${active.id}/proof`, {
        method: "POST",
        body: JSON.stringify({
          proof_type: "signature",
          data_base64: sig,
          meta: { format: "png" },
        }),
      });

      alert("Proof uploaded ✅");
    } catch (e) {
      setProofErr(e.message || "Proof upload failed");
    }
  }

  async function setStatusDelivered() {
    if (!active) return;
    try {
      await api(`/driver/orders/${active.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status: "DELIVERED" }),
      });
      await refresh();
      alert("Marked DELIVERED ✅");
    } catch (e) {
      alert(e.message || "Update failed");
    }
  }

  async function setStatusFailed(reason) {
    if (!active) return;
    try {
      await api(`/driver/orders/${active.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status: "FAILED", reason }),
      });
      await refresh();
      alert("Marked FAILED ✅");
    } catch (e) {
      alert(e.message || "Update failed");
    }
  }

  const routeText = useMemo(() => {
    if (!active) return "";
    const r = active.route || active?.payload?.route;
    if (!r) return "";
    try {
      return JSON.stringify(r, null, 2);
    } catch {
      return String(r);
    }
  }, [active]);

  const activeItems = useMemo(() => {
    if (!active) return [];
    // manifest has items directly, assigned has payload.items
    const items = active.items || active?.payload?.items || [];
    return Array.isArray(items) ? items : [];
  }, [active]);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Driver Portal</h1>
            <p className="mt-1 text-sm text-gray-600">
              Clean workflow: select order → add proof → deliver / fail.
            </p>
          </div>
          <button
            onClick={refresh}
            className="rounded-xl bg-black px-4 py-2 text-white font-semibold hover:opacity-90 disabled:opacity-50"
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {/* Tabs */}
        <div className="mt-5 flex gap-2">
          <button
            onClick={() => setTab("manifest")}
            className={`rounded-xl px-4 py-2 font-semibold border ${
              tab === "manifest" ? "bg-white shadow-sm" : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            Manifest (Today)
          </button>
          <button
            onClick={() => setTab("assigned")}
            className={`rounded-xl px-4 py-2 font-semibold border ${
              tab === "assigned" ? "bg-white shadow-sm" : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            All Assigned
          </button>
        </div>

        {err && (
          <div className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 border">
            {err}
          </div>
        )}

        {/* Controls */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            className="rounded-xl border px-3 py-2"
            placeholder="Search by Order ID / Client ID..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select
            className="rounded-xl border px-3 py-2"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All statuses</option>
            <option value="READY_FOR_DRIVER">READY_FOR_DRIVER</option>
            <option value="OUT_FOR_DELIVERY">OUT_FOR_DELIVERY</option>
            <option value="DELIVERED">DELIVERED</option>
            <option value="FAILED">FAILED</option>
          </select>

          <div className="rounded-xl border bg-white px-3 py-2 text-sm text-gray-700">
            <div className="font-semibold">Driver</div>
            <div className="font-mono text-xs">{manifest.driver_id || "-"}</div>
          </div>
        </div>

        {/* Main layout */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* List */}
          <div className="lg:col-span-1 rounded-2xl border bg-white shadow-sm overflow-hidden">
            <div className="p-3 border-b flex items-center justify-between">
              <div className="font-bold">Orders</div>
              <div className="text-xs text-gray-500">{list.length} items</div>
            </div>

            <div className="max-h-[70vh] overflow-auto">
              {list.length === 0 ? (
                <div className="p-6 text-sm text-gray-600">
                  No orders found. If you expect orders here, check{" "}
                  <span className="font-mono">assigned_driver_id</span> is set.
                </div>
              ) : (
                list.map((o) => (
                  <button
                    key={o.id}
                    onClick={() => {
                      setActive(o);
                      setPhotoDataUrl("");
                      setProofErr("");
                      clearSignature();
                    }}
                    className={`w-full text-left p-3 border-b hover:bg-gray-50 ${
                      active?.id === o.id ? "bg-gray-50" : "bg-white"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-xs text-gray-500">Order</div>
                        <div className="font-mono font-semibold">{o.id}</div>
                        <div className="mt-1 text-xs text-gray-500">
                          Client: <span className="font-mono">{o.client_id}</span>
                        </div>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badge(o.status)}`}>
                        {o.status}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Details */}
          <div className="lg:col-span-2 space-y-4">
            {!active ? (
              <div className="rounded-2xl border bg-white p-8 text-center text-gray-600 shadow-sm">
                Select an order to see details.
              </div>
            ) : (
              <>
                {/* Order card */}
                <div className="rounded-2xl border bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-xs text-gray-500">Selected Order</div>
                      <div className="font-mono text-xl font-extrabold">{active.id}</div>
                      <div className="mt-1 text-sm text-gray-600">
                        Client: <span className="font-mono">{active.client_id}</span>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-2">
                      <span className={`rounded-full px-3 py-1 text-xs font-bold ${badge(active.status)}`}>
                        {active.status}
                      </span>

                      <div className="text-xs text-gray-500">
                        Updated:{" "}
                        <span className="font-mono">{active.updated_at || "-"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-2xl border bg-gray-50 p-4">
                      <div className="text-sm font-bold text-gray-800">Destination</div>
                      <div className="mt-2 text-sm text-gray-700 font-mono">
                        {active.destination || active?.payload?.destination || "-"}
                      </div>

                      <div className="mt-4 text-sm font-bold text-gray-800">Items</div>
                      <div className="mt-2 space-y-2">
                        {activeItems.length === 0 ? (
                          <div className="text-sm text-gray-500">No items</div>
                        ) : (
                          activeItems.map((it, idx) => (
                            <div key={idx} className="flex items-center justify-between text-sm">
                              <div className="font-mono">{it.sku}</div>
                              <div className="font-semibold">x{it.qty}</div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    <div className="rounded-2xl border bg-gray-50 p-4">
                      <div className="text-sm font-bold text-gray-800">Route (PoC)</div>
                      <pre className="mt-2 max-h-48 overflow-auto rounded-xl bg-white border p-3 text-xs text-gray-700">
                        {routeText || "No route yet"}
                      </pre>
                    </div>
                  </div>
                </div>

                {/* Proof */}
                <div className="rounded-2xl border bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-lg font-bold">Proof of Delivery</div>
                      <div className="text-sm text-gray-600">
                        Upload photo (optional) + signature (required).
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={clearSignature}
                        className="rounded-xl border px-4 py-2 font-semibold hover:bg-gray-50"
                      >
                        Clear Signature
                      </button>
                      <button
                        onClick={uploadProof}
                        className="rounded-xl bg-black px-4 py-2 text-white font-semibold hover:opacity-90"
                      >
                        Upload Proof
                      </button>
                    </div>
                  </div>

                  {proofErr && (
                    <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 border">
                      {proofErr}
                    </div>
                  )}

                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-2xl border bg-gray-50 p-4">
                      <div className="text-sm font-bold text-gray-800">Photo</div>
                      <input
                        type="file"
                        accept="image/*"
                        className="mt-3 block w-full text-sm"
                        onChange={(e) => onPhotoPick(e.target.files?.[0])}
                      />
                      {photoDataUrl && (
                        <img
                          src={photoDataUrl}
                          alt="proof"
                          className="mt-3 w-full rounded-xl border object-cover max-h-56"
                        />
                      )}
                      {!photoDataUrl && (
                        <div className="mt-3 text-sm text-gray-500">
                          No photo selected.
                        </div>
                      )}
                    </div>

                    <div className="rounded-2xl border bg-gray-50 p-4">
                      <div className="text-sm font-bold text-gray-800">Signature</div>
                      <div className="mt-3 rounded-xl border bg-white overflow-hidden">
                        <canvas
                          ref={canvasRef}
                          width={700}
                          height={220}
                          className="w-full h-56 touch-none"
                          onPointerDown={startDraw}
                          onPointerMove={moveDraw}
                          onPointerUp={endDraw}
                          onPointerLeave={endDraw}
                        />
                      </div>
                      <div className="mt-2 text-xs text-gray-500">
                        Use mouse/touch to sign.
                      </div>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="rounded-2xl border bg-white p-5 shadow-sm">
                  <div className="text-lg font-bold">Actions</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={setStatusDelivered}
                      className="rounded-xl bg-green-600 px-4 py-2 text-white font-semibold hover:opacity-90"
                    >
                      Mark Delivered
                    </button>
                    <button
                      onClick={() => {
                        setFailReason("");
                        setFailOpen(true);
                      }}
                      className="rounded-xl bg-red-600 px-4 py-2 text-white font-semibold hover:opacity-90"
                    >
                      Mark Failed
                    </button>
                  </div>

                  <div className="mt-3 text-xs text-gray-500">
                    Tip: Upload proof first, then mark status.
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Failed modal */}
      <Modal
        open={failOpen}
        title="Mark as FAILED"
        onClose={() => setFailOpen(false)}
      >
        <div className="space-y-3">
          <div className="text-sm text-gray-700">
            Give a short reason (required).
          </div>
          <textarea
            className="w-full rounded-xl border px-3 py-2"
            rows={4}
            value={failReason}
            onChange={(e) => setFailReason(e.target.value)}
            placeholder="Recipient not available / Address incorrect / Package damaged..."
          />
          <div className="flex justify-end gap-2">
            <button
              className="rounded-xl border px-4 py-2 font-semibold hover:bg-gray-50"
              onClick={() => setFailOpen(false)}
            >
              Cancel
            </button>
            <button
              className="rounded-xl bg-red-600 px-4 py-2 text-white font-semibold hover:opacity-90"
              onClick={async () => {
                const r = failReason.trim();
                if (!r) return alert("Reason required");
                setFailOpen(false);
                await setStatusFailed(r);
              }}
            >
              Confirm Failed
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
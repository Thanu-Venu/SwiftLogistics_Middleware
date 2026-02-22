import { useState } from "react";
import { api } from "../api/client";

export default function CreateOrder() {
  const [destination, setDestination] = useState("Colombo");
  const [sku, setSku] = useState("A1");
  const [qty, setQty] = useState(1);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-4">Place Order</h1>

      {err && <div className="text-red-600 mb-3">{err}</div>}
      {msg && <div className="text-green-700 mb-3">{msg}</div>}

      <div className="grid gap-3 max-w-md">
        <input className="border rounded p-2" value={destination}
          onChange={e=>setDestination(e.target.value)} placeholder="Destination" />
        <input className="border rounded p-2" value={sku}
          onChange={e=>setSku(e.target.value)} placeholder="SKU" />
        <input className="border rounded p-2" type="number" value={qty}
          onChange={e=>setQty(parseInt(e.target.value || "1"))} placeholder="Qty" />

        <button className="rounded bg-black text-white p-2"
          onClick={async()=>{
            setErr(""); setMsg("");
            try {
              const res = await api("/orders", {
                method: "POST",
                body: JSON.stringify({ items: [{ sku, qty }], destination }),
              });
              setMsg(`Order created: ${res.order_id}`);
            } catch(e) {
              setErr(e.message);
            }
          }}>
          Create
        </button>
      </div>
    </div>
  );
}
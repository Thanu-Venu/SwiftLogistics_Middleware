import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useNavigate, Link } from "react-router-dom";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [client_id, setClientId] = useState("C");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl shadow p-6">
        <h1 className="text-2xl font-semibold mb-4">Register</h1>

        {err && <div className="mb-3 text-red-600">{err}</div>}

        <input className="w-full border rounded p-2 mb-3"
          placeholder="Client ID (e.g., C002)" value={client_id} onChange={e=>setClientId(e.target.value)} />
        <input className="w-full border rounded p-2 mb-3"
          placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} />
        <input className="w-full border rounded p-2 mb-4" type="password"
          placeholder="Password" value={password} onChange={e=>setPassword(e.target.value)} />

        <button className="w-full rounded bg-black text-white p-2"
          onClick={async()=>{
            setErr("");
            try { await register(client_id, email, password); nav("/"); }
            catch(e){ setErr(e.message); }
          }}>
          Create account
        </button>

        <div className="mt-4 text-sm">
          Already have account? <Link className="underline" to="/login">Login</Link>
        </div>
      </div>
    </div>
  );
}
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();

  const [clientId, setClientId] = useState("C003");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await register(clientId.trim(), email.trim(), password);
      nav("/dashboard"); // ✅ after register auto login
    } catch (e2) {
      setErr(e2.message || "Register failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white border rounded-2xl shadow-sm p-6">
        <h1 className="text-2xl font-bold">Create Account</h1>
        <p className="text-sm text-gray-600 mt-1">
          Register as a client and start placing orders.
        </p>

        {err && (
          <div className="mt-4 rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
            {err}
          </div>
        )}

        <form className="mt-5 space-y-3" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm font-medium text-gray-700">Client ID</label>
            <input
              className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
              placeholder="C003"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
            />
            <p className="text-xs text-gray-500 mt-1">
              Use existing client_id like <span className="font-mono">C001</span> if orders already exist.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
              placeholder="c003@test.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input
              className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
              type="password"
              placeholder="Pass@123"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>

          <button
            className="w-full rounded-xl bg-black text-white py-2 font-semibold hover:opacity-90 disabled:opacity-50"
            disabled={loading}
            type="submit"
          >
            {loading ? "Creating..." : "Register"}
          </button>
        </form>

        <div className="mt-4 text-sm text-gray-600">
          Already have an account?{" "}
          <Link className="text-black font-semibold underline" to="/login">
            Back to login
          </Link>
        </div>
      </div>
    </div>
  );
}
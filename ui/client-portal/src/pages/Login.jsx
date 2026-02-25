import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email.trim(), password);
      nav("/dashboard"); // ✅ after login
    } catch (e2) {
      setErr(e2.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white border rounded-2xl shadow-sm p-6">
        <h1 className="text-2xl font-bold">Client Login</h1>
        <p className="text-sm text-gray-600 mt-1">
          Sign in to create orders and track status.
        </p>

        {err && (
          <div className="mt-4 rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
            {err}
          </div>
        )}

        <form className="mt-5 space-y-3" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              className="mt-1 w-full rounded-xl border px-3 py-2 focus:outline-none focus:ring"
              placeholder="c002@test.com"
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
              autoComplete="current-password"
            />
          </div>

          <button
            className="w-full rounded-xl bg-black text-white py-2 font-semibold hover:opacity-90 disabled:opacity-50"
            disabled={loading}
            type="submit"
          >
            {loading ? "Signing in..." : "Login"}
          </button>
        </form>

        <div className="mt-4 text-sm text-gray-600">
          New user?{" "}
          <Link className="text-black font-semibold underline" to="/register">
            Create an account
          </Link>
        </div>
      </div>
    </div>
  );
}
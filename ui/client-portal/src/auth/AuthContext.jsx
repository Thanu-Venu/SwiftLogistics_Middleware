import React, { createContext, useContext, useEffect, useState } from "react";
import { api, setToken, clearToken, getToken } from "../api/client";

const API = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refreshMe() {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api("/auth/me");
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshMe();
  }, []);

  async function login(email, password) {
    const r = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!r.ok) {
      const t = await r.text();
      throw new Error(t || "Login failed");
    }

    const data = await r.json();

    // ✅ store token via helper
    setToken(data.access_token);

    // ✅ immediately load /me (optional but good UX)
    await refreshMe();

    return data;
  }

  async function register(client_id, email, password) {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ client_id, email, password }),
    });
    await login(email, password);
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
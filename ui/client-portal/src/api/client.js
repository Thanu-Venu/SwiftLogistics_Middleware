import { API_BASE } from "../config";

export function getToken() {
  return localStorage.getItem("access_token");
}

export function setToken(t) {
  if (t) localStorage.setItem("access_token", t);
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

export async function api(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const token = getToken();

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  // ✅ attach bearer token
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    // token invalid/expired -> wipe
    clearToken();
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }

  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}
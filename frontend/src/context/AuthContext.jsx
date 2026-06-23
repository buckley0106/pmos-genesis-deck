import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, formatApiErrorDetail } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = loading
  const [error, setError] = useState(null);

  const loadMe = useCallback(async () => {
    const token = localStorage.getItem("pmos_token");
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      localStorage.removeItem("pmos_token");
      setUser(null);
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  async function login(email, password) {
    try {
      setError(null);
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("pmos_token", data.token);
      setUser(data.user);
      return { ok: true };
    } catch (e) {
      const msg = formatApiErrorDetail(e.response?.data?.detail) || e.message;
      setError(msg);
      return { ok: false, error: msg };
    }
  }

  async function register(email, password, name) {
    try {
      setError(null);
      const { data } = await api.post("/auth/register", { email, password, name });
      localStorage.setItem("pmos_token", data.token);
      setUser(data.user);
      return { ok: true };
    } catch (e) {
      const msg = formatApiErrorDetail(e.response?.data?.detail) || e.message;
      setError(msg);
      return { ok: false, error: msg };
    }
  }

  function logout() {
    localStorage.removeItem("pmos_token");
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, error, login, register, logout, loadMe }}>{children}</AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);

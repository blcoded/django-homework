"use client";

import * as React from "react";
import { api, clearToken, getToken, setToken } from "@/lib/api";

interface User {
  id: number;
  email: string;
  display_name: string;
}

interface Household {
  id: number;
  name: string;
  timezone: string;
  invite_code?: string;
}

interface AuthContextType {
  user: User | null;
  household: Household | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  createHousehold: (name: string, timezone?: string) => Promise<Household>;
  joinHousehold: (inviteCode: string) => Promise<any>;
  refreshState: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [household, setHousehold] = React.useState<Household | null>(null);
  const [loading, setLoading] = React.useState(true);

  const refreshState = React.useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setHousehold(null);
      setLoading(false);
      return;
    }

    try {
      const userData = await api.auth.me();
      setUser(userData);

      const households = await api.households.list();
      if (households && households.length > 0) {
        setHousehold(households[0]);
      } else {
        setHousehold(null);
      }
    } catch (err) {
      clearToken();
      setUser(null);
      setHousehold(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refreshState();
  }, [refreshState]);

  const login = async (email: string, password: string) => {
    const res = await api.auth.login({ email, password });
    if (res.token) {
      setToken(res.token);
      await refreshState();
    }
  };

  const register = async (
    email: string,
    password: string,
    displayName?: string
  ) => {
    const res = await api.auth.register({
      email,
      password,
      display_name: displayName,
    });
    if (res.token) {
      setToken(res.token);
      await refreshState();
    }
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } catch {
      // ignore
    } finally {
      clearToken();
      setUser(null);
      setHousehold(null);
    }
  };

  const createHousehold = async (name: string, tz: string = "UTC") => {
    const newHousehold = await api.households.create({ name, timezone: tz });
    setHousehold(newHousehold);
    return newHousehold;
  };

  const joinHousehold = async (inviteCode: string) => {
    const res = await api.households.join(inviteCode);
    if (res.household) {
      setHousehold(res.household);
    }
    await refreshState();
    return res;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        household,
        loading,
        login,
        register,
        logout,
        createHousehold,
        joinHousehold,
        refreshState,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

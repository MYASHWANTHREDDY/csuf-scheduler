import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  getCsrfToken,
  getCurrentUser,
  login as loginApi,
  logout as logoutApi,
  normalizeError,
} from "../api/client";

const STORAGE_KEY = "csuf_scheduler_mobile_session";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [csrfToken, setCsrfToken] = useState("");
  const [initializing, setInitializing] = useState(true);

  const clearLocalSession = useCallback(async () => {
    setUser(null);
    setCsrfToken("");
    await AsyncStorage.removeItem(STORAGE_KEY);
  }, []);

  const persistSessionHint = useCallback(async (nextUser) => {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify({ userId: nextUser.id }));
  }, []);

  const bootstrapSession = useCallback(async () => {
    try {
      const sessionHint = await AsyncStorage.getItem(STORAGE_KEY);
      if (!sessionHint) {
        return;
      }
      const currentUser = await getCurrentUser();
      const token = await getCsrfToken();
      setUser(currentUser);
      setCsrfToken(token);
    } catch {
      await clearLocalSession();
    }
  }, [clearLocalSession]);

  useEffect(() => {
    let isMounted = true;
    const run = async () => {
      await bootstrapSession();
      if (isMounted) {
        setInitializing(false);
      }
    };
    run();
    return () => {
      isMounted = false;
    };
  }, [bootstrapSession]);

  const login = useCallback(
    async (email, password) => {
      try {
        const authPayload = await loginApi(email, password);
        setUser(authPayload);
        setCsrfToken(authPayload.csrf_token || "");
        await persistSessionHint(authPayload);
      } catch (error) {
        throw new Error(normalizeError(error));
      }
    },
    [persistSessionHint]
  );

  const logout = useCallback(async () => {
    try {
      await logoutApi(csrfToken);
    } catch {
      // no-op: clear local session even if server-side logout fails
    }
    await clearLocalSession();
  }, [clearLocalSession, csrfToken]);

  const value = useMemo(
    () => ({ user, csrfToken, initializing, login, logout }),
    [user, csrfToken, initializing, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
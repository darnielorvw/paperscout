import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
} from "react";
import { useNavigate } from "react-router";
import { apiFetch, UnauthorizedError } from "~/lib/api";

// Basierend auf dem UserPublic-Schema in FastAPI
export interface User {
  id: number;
  name: string;
  email: string;
  institution: string;
}

interface AuthContextType {
  user: User | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean; // Gibt an, ob der initiale Auth-Check läuft
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  const checkAuthStatus = useCallback(async () => {
    const token = localStorage.getItem("auth_token");
    if (token) {
      try {
        const userData = await apiFetch("/api/users/me", { method: "GET" }, false);
        setUser(userData);
      } catch (error) {
        if (error instanceof UnauthorizedError) {
          localStorage.removeItem("auth_token");
        }
        console.error("Auth check failed", error);
      }
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  const login = useCallback(async (token: string) => {
    localStorage.setItem("auth_token", token);
    const userData = await apiFetch("/api/users/me", { method: "GET" });
    setUser(userData);
    navigate("/");
  }, [navigate]);

  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem("auth_token");
    navigate("/login");
  }, [navigate]);

  const value = {
    user,
    login,
    logout,
    isAuthenticated: !!user,
    isLoading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
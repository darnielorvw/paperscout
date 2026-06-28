import { useEffect } from "react";
import { useAuth } from "~/context/auth-context";

export default function LogoutPage() {
  const { logout } = useAuth();

  useEffect(() => {
    logout();
  }, [logout]);

  // Zeige eine Ladeanzeige, während die Weiterleitung stattfindet.
  return <div>Logging out...</div>;
}
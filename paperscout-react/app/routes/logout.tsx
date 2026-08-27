import { useEffect } from "react";
import { useAuth } from "~/context/auth-context";

export default function LogoutPage() {
  const { logout } = useAuth();

  useEffect(() => {
    logout();
  }, [logout]);

  // Show a loading indicator while the redirect happens.
  return <div>Logging out...</div>;
}
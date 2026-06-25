import { useEffect } from "react";
import { useNavigate } from "react-router";

export default function LogoutPage() {
  const navigate = useNavigate();

  useEffect(() => {
    // In einer echten Anwendung würdest du hier den Auth-Token aus dem
    // Local Storage oder Auth-Context entfernen.
    // z.B. auth.logout();

    // Dann zur Login-Seite weiterleiten.
    navigate("/login");
  }, [navigate]);

  // Zeige eine Ladeanzeige, während die Weiterleitung stattfindet.
  return <div>Logging out...</div>;
}
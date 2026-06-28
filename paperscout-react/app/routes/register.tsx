import { Link, useNavigate } from "react-router";
import { AuthCard, type AuthField } from "~/components/auth-card";
import { apiFetch } from "~/lib/api";

export default function RegisterPage() {
  const navigate = useNavigate();

  const handleRegister = async (formData: FormData) => {
    const name = formData.get("name");
    const email = formData.get("email");
    const password = formData.get("password");

    if (
      typeof name !== "string" ||
      typeof email !== "string" ||
      typeof password !== "string"
    ) {
      throw new Error("Ungültige Eingabedaten.");
    }

    const response = await apiFetch(
      "/api/register",
      {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name, email, password }),
    });

    if (response.id) {
      navigate("/login");
    } else {
      throw new Error(response.detail || "Registrierung fehlgeschlagen.");
    }
  };

  const fields: AuthField[] = [
    { id: "name", name: "name", label: "Name", type: "text", required: true },
    { id: "email", name: "email", label: "E-Mail", type: "email", required: true },
    { id: "password", name: "password", label: "Passwort", type: "password", required: true },
  ];

  return (
    <AuthCard
      title="Konto erstellen"
      description="Erstelle ein neues Konto, um PaperScout zu nutzen."
      fields={fields}
      submitButtonText="Konto erstellen"
      onSubmit={handleRegister}
      footerContent={
        <p className="text-sm text-muted-foreground">
          Du hast bereits ein Konto?{" "}
          <Link to="/login" className="font-semibold text-primary">
            Anmelden
          </Link>
        </p>
      }
    />
  );
}
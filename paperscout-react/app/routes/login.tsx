import { Link } from "react-router";
import { AuthCard, type AuthField } from "~/components/auth-card";
import { useAuth } from "~/context/auth-context";
import { apiFetch } from "~/lib/api";

export default function LoginPage() {
  const { login } = useAuth();

  const handleLogin = async (formData: FormData) => {
    const email = formData.get("email");
    const password = formData.get("password");

    if (typeof email !== "string" || typeof password !== "string") {
      throw new Error("Ungültige Eingabedaten.");
    }

    const loginFormData = new URLSearchParams();
    loginFormData.append("username", email);
    loginFormData.append("password", password);

    const loginResponse = await apiFetch(
      "/api/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: loginFormData.toString(),
      },
      false,
    );

    if (!loginResponse.access_token) {
      throw new Error(loginResponse.detail || "Login fehlgeschlagen.");
    }

    await login(loginResponse.access_token);
  };

  const fields: AuthField[] = [
    { id: "email", name: "email", label: "E-Mail", type: "email", required: true },
    { id: "password", name: "password", label: "Passwort", type: "password", required: true },
  ];

  return (
    <AuthCard
      title="Anmeldung"
      description="Bitte melde dich an, um auf PaperScout zuzugreifen."
      fields={fields}
      submitButtonText="Anmelden"
      onSubmit={handleLogin}
      footerContent={
        <p className="text-sm text-muted-foreground">
          Du hast noch kein Konto?{" "}
          <Link to="/register" className="font-semibold text-primary">
            Registrieren
          </Link>
        </p>
      }
    />
  );
}
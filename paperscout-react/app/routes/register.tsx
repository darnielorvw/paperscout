import { useState } from "react";
import { Link } from "react-router";
import { AuthCard, type AuthField } from "~/components/auth-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "~/components/ui/card";
import { apiFetch } from "~/lib/api";

export default function RegisterPage() {
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);

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

    if (response.message) {
      setSubmittedEmail(email);
    } else {
      throw new Error(response.detail || "Registrierung fehlgeschlagen.");
    }
  };

  if (submittedEmail) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Fast geschafft!</CardTitle>
            <CardDescription className="my-2">
              Wir haben eine Bestätigungsmail an <strong>{submittedEmail}</strong> geschickt.
              Klicke auf den Link darin, um dein Konto zu aktivieren.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            <Link to="/login" className="font-semibold text-primary">
              Zurück zur Anmeldung
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

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
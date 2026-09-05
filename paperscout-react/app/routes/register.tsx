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
      throw new Error("Invalid input data.");
    }

    const response = await apiFetch<{ message?: string; detail?: string }>(
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
      throw new Error(response.detail || "Registration failed.");
    }
  };

  if (submittedEmail) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Almost done!</CardTitle>
            <CardDescription className="my-2">
              We've sent a confirmation email to <strong>{submittedEmail}</strong>.
              Click the link in it to activate your account.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            <Link to="/login" className="font-semibold text-primary">
              Back to login
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const fields: AuthField[] = [
    { id: "name", name: "name", label: "Name", type: "text", required: true },
    { id: "email", name: "email", label: "Email", type: "email", required: true },
    { id: "password", name: "password", label: "Password", type: "password", required: true },
  ];

  return (
    <AuthCard
      title="Create account"
      description="Create a new account to use PaperScout."
      fields={fields}
      submitButtonText="Create account"
      onSubmit={handleRegister}
      footerContent={
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-primary">
            Log in
          </Link>
        </p>
      }
    />
  );
}
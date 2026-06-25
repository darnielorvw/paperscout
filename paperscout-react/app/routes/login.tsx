import { useState } from "react";
import { Form, Link, useNavigate } from "react-router";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { apiFetch } from "~/lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const formData = new FormData(event.currentTarget);
    const email = formData.get("email");
    const password = formData.get("password");

    if (typeof email !== "string" || typeof password !== "string") {
      setError("Invalid form data");
      setIsSubmitting(false);
      return;
    }

    try {
      const loginFormData = new URLSearchParams();
      loginFormData.append("username", email);
      loginFormData.append("password", password);

      const response = await apiFetch("http://localhost:8000/api/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: loginFormData.toString(),
      });

      if (response.access_token) {
        // Hier könntest du den Token speichern (z.B. im AuthContext)
        navigate("/"); // Nach erfolgreichem Login weiterleiten
      } else {
        setError(response.detail || "Login failed");
      }
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex h-full w-full flex-col items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <Form onSubmit={handleSubmit}>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Anmeldung</CardTitle>
            <CardDescription>
              Bitte melde dich an, um auf PaperScout zuzugreifen.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">E-Mail</Label>
              <Input id="email" name="email" type="email" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Passwort</Label>
              <Input id="password" name="password" type="password" required />
            </div>
            {error && (
              <p className="text-sm text-red-500">{error}</p>
            )}
          </CardContent>
          <CardFooter className="flex-col gap-4">
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Melde an..." : "Anmelden"}
            </Button>
            <p className="text-sm text-muted-foreground">
              Du hast noch kein Konto?{" "}
              <Link to="/register" className="font-semibold text-primary">
                Registrieren
              </Link>
            </p>
          </CardFooter>
        </Form>
      </Card>
    </div>
  );
}
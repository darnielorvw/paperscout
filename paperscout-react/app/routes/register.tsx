import { useState } from "react";
import {
  Form,
  Link,
  useNavigate,
} from "react-router";
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

export default function RegisterPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.ChangeEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const formData = new FormData(event.currentTarget);
    const name = formData.get("name");
    const email = formData.get("email");
    const password = formData.get("password");

    if (
      typeof name !== "string" ||
      typeof email !== "string" ||
      typeof password !== "string" 
    ) {
      setError("Ungültige Eingabe.");
      setIsSubmitting(false);
      return;
    }

    try {
      console.log(JSON.stringify({ name, email, password }))
      const response = await apiFetch("http://localhost:8000/api/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name, email, password }),
      });

      if (response.id) {
        navigate("/login"); // Nach Erfolg zur Login-Seite weiterleiten
      } else {
        setError(response.detail || "Registrierung fehlgeschlagen.");
      }
    } catch (err: any) {
      setError(err.message || "Registrierung fehlgeschlagen.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex h-full w-full flex-col items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <Form onSubmit={handleSubmit}>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Konto erstellen</CardTitle>
            <CardDescription>
              Erstelle ein neues Konto, um PaperScout zu nutzen.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" name="name" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">E-Mail</Label>
              <Input id="email" name="email" type="email" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Passwort</Label>
              <Input id="password" name="password" type="password" required />
            </div>
            
            {error && <p className="text-sm text-red-500">{error}</p>}
          </CardContent>
          <CardFooter className="flex-col gap-4">
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Erstelle..." : "Konto erstellen"}
            </Button>
            <p className="text-sm text-muted-foreground">
              Du hast bereits ein Konto?{" "}
              <Link to="/login" className="font-semibold text-primary">
                Anmelden
              </Link>
            </p>
          </CardFooter>
        </Form>
      </Card>
    </div>
  );
}
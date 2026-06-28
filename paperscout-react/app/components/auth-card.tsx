import { useState } from "react";
import { Form } from "react-router";
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

export interface AuthField {
  id: string;
  name: string;
  label: string;
  type: "text" | "email" | "password";
  required?: boolean;
}

interface AuthCardProps {
  title: string;
  description: string;
  fields: AuthField[];
  submitButtonText: string;
  footerContent: React.ReactNode;
  onSubmit: (formData: FormData) => Promise<void>;
}

export function AuthCard({
  title,
  description,
  fields,
  submitButtonText,
  footerContent,
  onSubmit,
}: AuthCardProps) {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const formData = new FormData(event.currentTarget);

    try {
      await onSubmit(formData);
    } catch (err: any) {
      setError(err.message || "Ein unbekannter Fehler ist aufgetreten.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex h-full w-full flex-col items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <Form onSubmit={handleSubmit}>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">{title}</CardTitle>
            <CardDescription className="my-2">{description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 mb-4">
            {fields.map((field) => (
              <div key={field.id} className="space-y-2">
                <Label htmlFor={field.id}>{field.label}</Label>
                <Input
                  id={field.id}
                  name={field.name}
                  type={field.type}
                  required={field.required}
                />
              </div>
            ))}
            {error && <p className="text-sm text-red-500">{error}</p>}
          </CardContent>
          <CardFooter className="flex-col gap-4">
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Bitte warten..." : submitButtonText}
            </Button>
            {footerContent}
          </CardFooter>
        </Form>
      </Card>
    </div>
  );
}
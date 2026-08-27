import { Link, useSearchParams } from "react-router";
import { AuthCard, type AuthField } from "~/components/auth-card";
import { useAuth } from "~/context/auth-context";
import { apiFetch } from "~/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const [searchParams] = useSearchParams();
  const justVerified = searchParams.get("verified") === "true";

  const handleLogin = async (formData: FormData) => {
    const email = formData.get("email");
    const password = formData.get("password");

    if (typeof email !== "string" || typeof password !== "string") {
      throw new Error("Invalid input data.");
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
    { id: "email", name: "email", label: "Email", type: "email", required: true },
    { id: "password", name: "password", label: "Password", type: "password", required: true },
  ];

  return (
    <AuthCard
      title="Login"
      description={
        justVerified
          ? "Email confirmed! You can now log in."
          : "Please log in to access PaperScout."
      }
      fields={fields}
      submitButtonText="Sign in"
      onSubmit={handleLogin}
      footerContent={
        <p className="text-sm text-muted-foreground">
          Don't have an account yet?{" "}
          <Link to="/register" className="font-semibold text-primary">
            Register
          </Link>
        </p>
      }
    />
  );
}
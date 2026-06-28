import { AppHeader } from "~/components/app-header";

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col h-svh">
      <AppHeader />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

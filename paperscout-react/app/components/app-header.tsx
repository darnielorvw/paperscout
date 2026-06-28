import { LogOutIcon } from "lucide-react";
import { ModeToggle } from "~/components/mode-toggle";
import { SidebarTrigger } from "~/components/ui/sidebar";
import { useAuth } from "~/context/auth-context";
import { Button } from "./ui/button";

interface AppHeaderProps {
  showSidebarTrigger?: boolean;
}

export function AppHeader({ showSidebarTrigger = false }: AppHeaderProps) {
  const { logout } = useAuth();

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      {showSidebarTrigger && <SidebarTrigger />}
      <span className="text-lg font-bold">PaperScout</span>
      <div className="ml-auto">
        <ModeToggle />

        <Button
          variant="outline"
          onClick={logout}
          className="ml-4"
        >
          <LogOutIcon className="size-4" />
          Logout
        </Button>
      </div>
    </header>
  );
}

import { LogOutIcon } from "lucide-react";
import { useMemo } from "react";
import { ModeToggle } from "~/components/mode-toggle";
import { SidebarTrigger } from "~/components/ui/sidebar";
import { useAuth } from "~/context/auth-context";
import { useProfiles } from "~/context/profile-context";
import type { RadioItem } from "./radio-group";
import { HorizontalRadioGroup } from "./radio-group";
import { Button } from "./ui/button";

interface AppHeaderProps {
  showSidebarTrigger?: boolean;
  showProfiles?: boolean;
}

function ProfileSelector() {
  const { profiles, activeProfileId, applyProfile, clearActiveProfile } = useProfiles();

  const profileItems: RadioItem[] = useMemo(() => [
    { value: 'default', title: 'Default' },
    ...profiles.map(profile => ({
      value: profile.id.toString(),
      title: profile.name,
    }))
  ], [profiles]);

  const handleProfileChange = (value: string) => {
    if (value === 'default') {
      clearActiveProfile();
    } else {
      applyProfile(parseInt(value, 10));
    }
  };

  if (profileItems.length <= 1) {
    return null; // Zeige nichts an, wenn nur "Default" vorhanden ist
  }

  return (
    <HorizontalRadioGroup
      items={profileItems}
      value={activeProfileId?.toString() ?? 'default'}
      onValueChange={handleProfileChange}
    />
  );
}

export function AppHeader({ showSidebarTrigger = false, showProfiles = false }: AppHeaderProps) {
  const { logout } = useAuth();

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      {showSidebarTrigger && <SidebarTrigger />}
      <span className="text-lg font-bold shrink-0">PaperScout</span>
      <div className="flex-1 flex justify-start min-w-0">
        {showProfiles && <ProfileSelector />}
      </div>
      <div className="ml-auto flex items-center shrink-0">
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

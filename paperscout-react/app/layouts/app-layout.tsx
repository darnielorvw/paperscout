import { AppHeader } from "~/components/app-header";
import { AppSidebar } from "~/components/app-sidebar";
import { SidebarInset, SidebarProvider } from "~/components/ui/sidebar";
import { ProfileProvider } from "~/context/profile-context";
import { SearchProvider } from "~/context/search-context";

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SearchProvider>
      <ProfileProvider>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset className="flex h-svh flex-col overflow-hidden">
            <AppHeader showSidebarTrigger={true} showProfiles={true}/>

            <main className="flex-1 min-h-0 p-4 md:p-4">{children}</main>
          </SidebarInset>
        </SidebarProvider>
      </ProfileProvider>
    </SearchProvider>
  );
}

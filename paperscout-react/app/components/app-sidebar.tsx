import { UserIcon } from "lucide-react";
import * as React from "react";
import { NavLink, useLocation } from "react-router";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "~/components/ui/sidebar";
import { useAuth } from "~/context/auth-context";
import { useSearch } from "~/context/search-context";
import { buildResultsUrl } from "~/lib/search-utils";

const data = [
  {
    title: "Input",
    items: [
      {
        title: "Select Journals",
        url: "/#journals",
      },
      {
        title: "Select Time Range",
        url: "/#range",
      },
      {
        title: "Search",
        url: "/#search",
      },
    ],
  },
  {
    title: "Output",
    items: [
      {
        title: "Results",
        url: "/results",
      },
    ],
  },
  {
    title: "Settings",
    items: [
      {
        title: "Profiles",
        url: "/profiles",
      },
    ],
  },
];

const adminGroup = {
  title: "Admin",
  items: [
    {
      title: "Import Journals",
      url: "/admin",
    },
  ],
};

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation();
  const { user } = useAuth();
  const { rowSelection, date, searchTerm, isInitialized } = useSearch();
  const [isMounted, setIsMounted] = React.useState(false);

  const sidebarGroups = user?.is_admin ? [...data, adminGroup] : data;

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  // Build the results URL based on the global state.
  // useMemo ensures this is only recalculated on changes.
  const resultsUrl = React.useMemo(() => {
    if (!isInitialized) return "/results"; // Wait until the state has been loaded from storage
    return buildResultsUrl({ rowSelection, date, searchTerm });
  }, [rowSelection, date, searchTerm, isInitialized]);

  return (
    <Sidebar {...props}>
      <SidebarContent>
        {sidebarGroups.map((item) => (
          <SidebarGroup key={item.title}>
            {item.title && <SidebarGroupLabel>{item.title}</SidebarGroupLabel>}
            <SidebarGroupContent>
              <SidebarMenu>
                {item.items.map((subItem, index) => {
                  // Before hydration we assume (like the server) that there is no hash
                  const hash = isMounted ? location.hash : "";
                  const normalizedHash = subItem.url.startsWith("/#")
                    ? subItem.url.replace("/", "")
                    : "";

                  let finalUrl = subItem.url;
                  // If this is the "Results" link and we're on the home page,
                  // build the URL with the data from session storage.
                  if (subItem.url === "/results") {
                    finalUrl = resultsUrl;
                  }

                  // Active if the URL hash matches OR if there's no hash at all and this is the first item.
                  const isActive =
                    location.pathname === subItem.url ||
                    (location.pathname === "/" &&
                      (hash === normalizedHash || (!hash && index === 0)));
                  return (
                    <SidebarMenuItem key={subItem.title} className="w-full">
                      <SidebarMenuButton
                        asChild
                        isActive={isActive}
                        className="w-full justify-start"
                      >
                        <NavLink to={finalUrl}>{subItem.title}</NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              size="lg"
              className="w-full data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <NavLink to="/account">
                <div className="flex size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <UserIcon className="size-4" />
                </div>
                <div className="flex flex-col flex-1 min-w-0 text-left leading-tight">
                  <span className="truncate text-sm font-medium">
                    {user?.name}
                  </span>
                  <span className="truncate text-xs text-sidebar-foreground/60">
                    {user?.email}
                  </span>
                </div>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

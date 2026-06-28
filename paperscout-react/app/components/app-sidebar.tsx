import * as React from "react";
import { NavLink, useLocation } from "react-router";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "~/components/ui/sidebar";
import { useSearch } from "~/context/search-context";
import { buildResultsUrl } from "~/lib/search-utils";

// Dies sind Beispieldaten.
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
    title: "Results",
    items: [
      {
        title: "Results",
        url: "/results",
      }
    ],
  },
];

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation();
  const { rowSelection, date, searchTerm, isInitialized } = useSearch();
  const [isMounted, setIsMounted] = React.useState(false);

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  // Baue die Results-URL basierend auf dem globalen Zustand.
  // useMemo sorgt dafür, dass dies nur bei Änderungen neu berechnet wird.
  const resultsUrl = React.useMemo(() => {
    if (!isInitialized) return "/results"; // Warten, bis der Zustand aus dem Storage geladen ist
    return buildResultsUrl({ rowSelection, date, searchTerm });
  }, [rowSelection, date, searchTerm, isInitialized]);

  return (
    <Sidebar {...props}>
      <SidebarContent>
        {data.map((item) => (
          <SidebarGroup key={item.title}>
            <SidebarGroupLabel>{item.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {item.items.map((subItem, index) => {
                  // Vor der Hydration gehen wir (wie der Server) von keinem Hash aus
                  const hash = isMounted ? location.hash : "";
                  const normalizedHash = subItem.url.startsWith("/#")
                    ? subItem.url.replace("/", "")
                    : "";

                  let finalUrl = subItem.url;
                  // Wenn es der "Results"-Link ist und wir auf der Startseite sind,
                  // bauen wir die URL mit den Daten aus dem Session Storage.
                  if (subItem.url === "/results") {
                    finalUrl = resultsUrl;
                  }

                  // Aktiv, wenn der URL-Hash übereinstimmt ODER wenn gar kein Hash da ist und es das erste Item ist.
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
      <SidebarRail />
    </Sidebar>
  );
}

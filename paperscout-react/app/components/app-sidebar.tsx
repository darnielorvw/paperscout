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
      },
      {
        title: "Settings",
        url: "/test",
      }
    ],
  },
];

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation();
  const [isMounted, setIsMounted] = React.useState(false);

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

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
                  
                  // Aktiv, wenn der URL-Hash übereinstimmt ODER wenn gar kein Hash da ist und es das erste Item ist.
                  const isActive =
                    location.pathname === "/" &&
                    (hash === subItem.url.replace("/", "") ||
                      (!hash && index === 0));

                  return (
                    <SidebarMenuItem key={subItem.title}>
                      <SidebarMenuButton asChild isActive={isActive}>
                        <NavLink to={subItem.url}>{subItem.title}</NavLink>
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

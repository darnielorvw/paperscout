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

// This is sample data.
const data = {
  navMain: [
    {
      title: "Menü",
      url: "#",
      items: [
        {
          title: "Suche öffnen",
          url: "/#journals",
        },
        {
          title: "Einstellungen",
          url: "/#search",
        },
        {
          title: "Abmelden",
          url: "/#logout",
        },
      ],
    },
  ],
};

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation();

  return (
    <Sidebar {...props}>
      <SidebarContent>
        {data.navMain.map((item) => (
          <SidebarGroup key={item.title}>
            <SidebarGroupLabel>{item.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {item.items.map((subItem, index) => {
                  // Aktiv, wenn der URL-Hash übereinstimmt ODER wenn gar kein Hash da ist und es das erste Item ist.
                  const isActive =
                    location.pathname === "/" &&
                    (location.hash === subItem.url.replace("/", "") ||
                      (!location.hash && index === 0));

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

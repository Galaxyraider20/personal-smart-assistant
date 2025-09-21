"use client";
import logoUrl from "../assets/logo.svg";
import {
  Sidebar,
  SidebarItem,
  SidebarItemGroup,
  SidebarItems,
  SidebarLogo,
  createTheme
} from "flowbite-react";
import { HiHome, HiChatAlt2, HiCalendar, HiCog } from "react-icons/hi";
const sidebarTheme = {
  root: {
    base: "h-screen",
    collapsed: {
      on: "w-16",
      off: "w-64",
    },
    inner:
      "h-full overflow-y-auto overflow-x-hidden rounded bg-slate-800 px-3 py-4 dark:bg-slate-800",
  },
};
export default function DefaultSidebar() {
  return (
    <Sidebar 
      theme={sidebarTheme}
      applyTheme={{ root: { base: "replace" } }}
      aria-label="App sidebar"
    >
      <SidebarLogo href="#" img={logoUrl} imgAlt="Flowbite logo">
        <span className="text-lg font-semibold text-white">Calvera</span>
      </SidebarLogo>
      <SidebarItems>
        <SidebarItemGroup>
          <SidebarItem
            href="#"
            icon={HiHome}
            className="text-base font-medium tracking-wide hover:text-white"
          >
            Home
          </SidebarItem>

          <SidebarItem
            href="#chat"
            icon={HiChatAlt2}
            className="text-base font-medium tracking-wide hover:text-white"
          >
            Chat
          </SidebarItem>

          <SidebarItem
            href="#calendar"
            icon={HiCalendar}
            className="text-base font-medium tracking-wide hover:text-white"
          >
            Calendar
          </SidebarItem>
          <SidebarItem
            href="#settings"
            icon={HiCog}
            className="text-base font-medium tracking-wide hover:text-white"
          >
            Settings
          </SidebarItem>
          
        </SidebarItemGroup>
      </SidebarItems>
    </Sidebar>
  );
}

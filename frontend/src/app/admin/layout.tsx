"use client";

import React from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePathname, useRouter } from "next/navigation";
import { Title } from "@/components/ui/text/Title";

// Define the admin routes and their display names
const adminRoutes = {
  dashboard: { path: "/admin", name: "Dashboard" },
  analysis: { path: "/admin/analysis", name: "Analysis" },
  "field-harmonization": {
    path: "/admin/field-harmonization",
    name: "Field Harmonization",
  },
  scrape: { path: "/admin/scrape", name: "Scraping" },
  tasks: { path: "/admin/tasks", name: "Tasks" },
};

export default function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const pathname = usePathname();
  const router = useRouter();

  const getTabValue = () => {
    // Find the route key whose path matches the start of the current pathname
    const currentRoute = Object.entries(adminRoutes).find(([key, route]) => {
      // Exact match for dashboard, startsWith for others
      return key === "dashboard"
        ? pathname === route.path
        : pathname.startsWith(route.path);
    });
    return currentRoute ? currentRoute[0] : "dashboard"; // Return the key or default
  };

  const handleTabChange = (value: string) => {
    const route = adminRoutes[value as keyof typeof adminRoutes];
    if (route) {
      router.push(route.path);
    }
  };

  return (
    <div className="container mx-auto p-4">
      <Title className="mb-8">Admin Dashboard</Title>

      <Tabs
        value={getTabValue()}
        onValueChange={handleTabChange}
        className="mb-8"
      >
        <TabsList className="flex h-auto flex-wrap justify-start">
          {/* Generate TabsTrigger from adminRoutes */}
          {Object.entries(adminRoutes).map(([key, route]) => (
            <TabsTrigger key={key} value={key} className="cursor-pointer">
              {route.name}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {children}
    </div>
  );
}

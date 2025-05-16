"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/AuthProvider";
import { Skeleton } from "@/components/ui/skeleton";

const navItems = [
  { name: "Home", href: "/" },
  { name: "Listings", href: "/listings" },
  { name: "Watched Searches", href: "/watched" },
  { name: "Admin", href: "/admin", adminOnly: true },
];

export default function Navbar() {
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  return (
    <nav className="bg-primary text-primary-foreground shadow-md">
      <div className="container mx-auto flex items-center justify-between px-4 py-3">
        <div className="flex items-center space-x-4">
          <Link href="/" className="text-xl font-bold">
            Reduse
          </Link>
          <div className="hidden items-center space-x-2 md:flex">
            {navItems.map((item) => {
              if (item.adminOnly && (!isAuthenticated || !user?.is_superuser)) {
                return null;
              }
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    pathname === item.href
                      ? "bg-primary-foreground text-primary"
                      : "hover:bg-primary-foreground/10",
                  )}
                >
                  {item.name}
                </Link>
              );
            })}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {isLoading ? (
            <>
              <Skeleton className="h-8 w-20 rounded-md" />
              <Skeleton className="h-8 w-20 rounded-md" />
            </>
          ) : isAuthenticated ? (
            <>
              <span className="mr-2 hidden text-sm sm:inline">
                Welcome, {user?.email}
              </span>
              <Button variant="secondary" size="sm" onClick={logout}>
                Logout
              </Button>
            </>
          ) : (
            <>
              <Button variant="secondary" size="sm" asChild>
                <Link href="/login">Login</Link>
              </Button>
              <Button variant="secondary" size="sm" asChild>
                <Link href="/register">Register</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

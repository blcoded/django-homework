"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { navigationItems } from "./nav-items";

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      data-testid="desktop-sidebar"
      className={cn(
        "hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 border-r bg-card shadow-sm z-30",
        className
      )}
    >
      <div className="flex h-16 items-center border-b px-6">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg text-primary tracking-tight">
          <Sparkles className="h-6 w-6 text-primary" />
          <span>RoommateOS</span>
        </Link>
      </div>

      <div className="flex flex-1 flex-col justify-between overflow-y-auto px-4 py-6">
        <nav className="space-y-1.5" aria-label="Main Navigation">
          {navigationItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.name}
                href={item.href}
                data-testid={`nav-item-${item.name.toLowerCase()}`}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto border-t pt-4">
          <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
            <p className="font-semibold text-foreground">Equal Household</p>
            <p className="mt-0.5">Automated fair chore rotation without household bosses.</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

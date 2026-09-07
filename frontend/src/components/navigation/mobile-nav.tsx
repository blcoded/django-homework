"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { navigationItems } from "./nav-items";

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav
      data-testid="mobile-nav"
      aria-label="Mobile Navigation"
      className="fixed bottom-0 left-0 right-0 z-30 flex h-16 items-center justify-around border-t bg-card px-2 shadow-lg md:hidden"
    >
      {navigationItems.map((item) => {
        const isActive =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        const Icon = item.icon;

        return (
          <Link
            key={item.name}
            href={item.href}
            data-testid={`mobile-nav-${item.name.toLowerCase()}`}
            className={cn(
              "flex flex-col items-center justify-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors",
              isActive
                ? "text-primary font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className={cn("h-5 w-5", isActive && "text-primary")} />
            <span>{item.name}</span>
          </Link>
        );
      })}
    </nav>
  );
}

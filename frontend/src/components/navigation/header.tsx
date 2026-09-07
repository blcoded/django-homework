"use client";

import { Bell, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  householdName?: string;
  onMenuToggle?: () => void;
}

export function Header({ householdName = "Our Household", onMenuToggle }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 w-full items-center justify-between border-b bg-background/95 px-4 backdrop-blur sm:px-6 md:pl-72">
      <div className="flex items-center gap-3">
        <Link href="/" className="md:hidden flex items-center gap-1.5 font-bold text-primary">
          <Sparkles className="h-5 w-5" />
          <span className="text-base">RoommateOS</span>
        </Link>
        <div className="hidden sm:flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">{householdName}</span>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
            Active
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="h-4 w-4 text-muted-foreground" />
        </Button>
      </div>
    </header>
  );
}

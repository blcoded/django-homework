import {
  Home,
  CheckSquare,
  Activity,
  BarChart2,
  Users,
  LucideIcon,
} from "lucide-react";

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
}

export const navigationItems: NavItem[] = [
  { name: "Home", href: "/", icon: Home },
  { name: "Chores", href: "/chores", icon: CheckSquare },
  { name: "Activity", href: "/activity", icon: Activity },
  { name: "Stats", href: "/stats", icon: BarChart2 },
  { name: "Household", href: "/household", icon: Users },
];

import type { ComponentType } from "react";
import {
  ArrowLeftRight,
  CalendarDays,
  ChefHat,
  House,
  Landmark,
  LayoutDashboard,
  ListChecks,
  NotebookPen,
  Package,
  Refrigerator,
  Repeat,
  Wallet,
} from "lucide-react";

import { IconCalendarCheck, IconMap, IconSprout } from "../components/gardnr/ui";

export interface ModuleNavItem {
  to: string;
  label: string;
  /** Bottom-nav label where `label` doesn't fit a fifth of a 390px screen. */
  shortLabel?: string;
  /** Any icon component taking a pixel `size` -- Lucide icons, or a module's own set
   * (gardnr's redesign draws its own). */
  icon: ComponentType<{ size?: number | string; className?: string; strokeWidth?: number | string }>;
  /** Exact match only -- for a tab whose path is a prefix of its sibling tabs' paths. */
  end?: boolean;
  /** For a tab that also owns a differently-spelled detail route (listr's `lijst/:id` under
   * "Lijsten"), where prefix matching alone can't tell "still under this tab" from a sibling. */
  matches?: (pathname: string) => boolean;
}

/** Each module's sections, in tab order -- the single list both the desktop tab strip and the
 * mobile bottom nav render from, so the two can't drift out of order. */
export const MODULE_NAV: Record<string, ModuleNavItem[]> = {
  gainr: [
    { to: "/", end: true, label: "Home", icon: House },
    { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
    { to: "/journal", label: "Journal", icon: NotebookPen },
  ],
  gripr: [
    { to: "/gripr", end: true, label: "Accounts", icon: Landmark },
    { to: "/gripr/transactions", label: "Transactions", icon: ArrowLeftRight },
    { to: "/gripr/budget", label: "Budget", icon: Wallet },
    { to: "/gripr/recurring", label: "Recurring", icon: Repeat },
    { to: "/gripr/overview", label: "Overview", icon: LayoutDashboard },
  ],
  listr: [
    {
      to: "/listr",
      label: "Lijsten",
      icon: ListChecks,
      matches: (p) => p === "/listr" || p.startsWith("/listr/lijst/") || ["/listr/bestellingen", "/listr/winkelwagen", "/listr/aanbiedingen"].includes(p),
    },
    {
      to: "/listr/recepten",
      label: "Recepten",
      icon: ChefHat,
      matches: (p) => p.startsWith("/listr/recepten") || p.startsWith("/listr/recept/"),
    },
    { to: "/listr/weekplanner", label: "Weekplanner", shortLabel: "Week", icon: CalendarDays },
    { to: "/listr/producten", label: "Producten", icon: Package },
    { to: "/listr/voorraad", label: "Voorraad", icon: Refrigerator },
  ],
  gardnr: [
    { to: "/gardnr/vandaag", label: "Vandaag", icon: IconCalendarCheck },
    {
      to: "/gardnr",
      label: "Tuinen",
      icon: IconMap,
      matches: (p) => p === "/gardnr" || p.startsWith("/gardnr/areas/"),
    },
    { to: "/gardnr/plants", label: "Planten", icon: IconSprout },
  ],
};

export function isNavItemActive(item: ModuleNavItem, pathname: string): boolean {
  if (item.matches) return item.matches(pathname);
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(item.to + "/");
}

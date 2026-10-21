import type { ComponentType } from "react";
import {
  Archive,
  ArrowLeftRight,
  CalendarCheck2,
  CalendarDays,
  ChefHat,
  Coins,
  Dumbbell,
  History,
  House,
  Inbox,
  Landmark,
  LayoutDashboard,
  ListChecks,
  NotebookPen,
  Package,
  Refrigerator,
  Repeat,
  StickyNote,
  Wallet,
} from "lucide-react";

import { IconCalendarCheck, IconMap, IconSprout } from "../components/gardnr/ui";
import { msg } from "../i18n";

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
  vandaag: [],
  gainr: [
    { to: "/gainr", end: true, label: msg("Home"), icon: House },
    { to: "/transactions", label: msg("Transactions"), icon: ArrowLeftRight },
    { to: "/income", label: msg("Income"), icon: Coins },
    { to: "/journal", label: msg("Journal"), icon: NotebookPen },
  ],
  gripr: [
    { to: "/gripr", end: true, label: msg("Accounts"), icon: Landmark },
    { to: "/gripr/transactions", label: msg("Transactions"), icon: ArrowLeftRight },
    { to: "/gripr/budget", label: msg("Budget"), icon: Wallet },
    { to: "/gripr/recurring", label: msg("Recurring"), icon: Repeat },
    { to: "/gripr/overview", label: msg("Overview"), icon: LayoutDashboard },
  ],
  listr: [
    {
      to: "/listr",
      label: msg("Lijsten"),
      icon: ListChecks,
      matches: (p) => p === "/listr" || p.startsWith("/listr/lijst/") || ["/listr/bestellingen", "/listr/winkelwagen", "/listr/aanbiedingen"].includes(p),
    },
    {
      to: "/listr/recepten",
      label: msg("Recepten"),
      icon: ChefHat,
      matches: (p) => p.startsWith("/listr/recepten") || p.startsWith("/listr/recept/"),
    },
    { to: "/listr/weekplanner", label: msg("Weekplanner"), shortLabel: msg("Week"), icon: CalendarDays },
    { to: "/listr/producten", label: msg("Producten"), icon: Package },
    { to: "/listr/voorraad", label: msg("Voorraad"), icon: Refrigerator },
  ],
  gardnr: [
    { to: "/gardnr/vandaag", label: msg("Vandaag"), icon: IconCalendarCheck },
    {
      to: "/gardnr",
      label: msg("Tuinen"),
      icon: IconMap,
      matches: (p) => p === "/gardnr" || p.startsWith("/gardnr/areas/"),
    },
    { to: "/gardnr/plants", label: msg("Planten"), icon: IconSprout },
  ],
  trainr: [
    { to: "/trainr", end: true, label: msg("Planner"), icon: CalendarDays },
    { to: "/trainr/historie", label: msg("Historie"), icon: History },
    { to: "/trainr/overzicht", label: msg("Overzicht"), icon: LayoutDashboard },
    { to: "/trainr/oefeningen", label: msg("Oefeningen"), icon: Dumbbell },
  ],
  taskr: [{ to: "/taskr", end: true, label: msg("Agenda"), icon: CalendarCheck2 }],
  briefr: [
    { to: "/briefr", end: true, label: msg("Inbox"), icon: Inbox },
    { to: "/briefr/archive", label: msg("Archive"), icon: Archive },
  ],
  notr: [
    { to: "/notr", end: true, label: msg("Notes"), icon: StickyNote },
    { to: "/notr/archive", label: msg("Archive"), icon: Archive },
  ],
};

export function isNavItemActive(item: ModuleNavItem, pathname: string): boolean {
  if (item.matches) return item.matches(pathname);
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(item.to + "/");
}

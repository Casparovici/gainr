import { Link, useLocation } from "react-router-dom";

import { isNavItemActive, type ModuleNavItem } from "../../config/moduleNav";

/** The page kit's bottom bar on a phone (gardnr, listr): white, 80px tall, a 64x32 soft pill in
 * the module's brand colour behind the active item. `badges` puts a count on an item (keyed by
 * its `to`), e.g. gardnr's overdue tasks on Vandaag, so it's visible from any page of the module. */
export default function KitBottomNav({
  items,
  label,
  badges = {},
}: {
  items: ModuleNavItem[];
  label: string;
  badges?: Record<string, { count: number; label: string }>;
}) {
  const { pathname } = useLocation();

  return (
    <nav
      aria-label={label}
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-ui-border bg-ui-surface px-2 pb-[env(safe-area-inset-bottom)] sm:hidden"
    >
      {items.map((item) => {
        const active = isNavItemActive(item, pathname);
        const Icon = item.icon;
        const badge = badges[item.to];
        return (
          <Link
            key={item.to}
            to={item.to}
            aria-current={active ? "page" : undefined}
            className={`relative flex h-20 min-w-0 flex-1 flex-col items-center gap-1 pt-2 ${active ? "text-ui-brand-strong" : "text-ui-muted"}`}
          >
            <span className={`flex h-8 w-16 items-center justify-center rounded-full ${active ? "bg-ui-brand-soft" : ""}`}>
              <Icon size={22} />
            </span>
            <span className={`truncate text-xs ${active ? "font-semibold" : "font-medium"}`}>{item.shortLabel ?? item.label}</span>
            {badge && badge.count > 0 && (
              <span
                className="absolute left-[calc(50%+12px)] top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-[9px] bg-ui-late px-1 text-[11px] font-bold text-white"
                aria-label={badge.label}
              >
                {badge.count}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}

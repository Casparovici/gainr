import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

import ModuleSwitcher from "./components/ModuleSwitcher";
import PortfolioSwitcher from "./components/PortfolioSwitcher";
import ModuleIndicators from "./components/ModuleIndicators";
import ThemeToggle from "./components/ThemeToggle";
import { activeModule } from "./config/modules";
import { isNavItemActive, MODULE_NAV } from "./config/moduleNav";
import { useModuleBranding } from "./hooks/useModuleBranding";
import Home from "./pages/Home";
import Journal from "./pages/Journal";
import Transactions from "./pages/Transactions";
import ListrInventory from "./pages/listr/Inventory";
import ListrPicnicCart from "./pages/listr/PicnicCart";
import ListrPicnicOffers from "./pages/listr/PicnicOffers";
import ListrPicnicOrders from "./pages/listr/PicnicOrders";
import ListrListDetail from "./pages/listr/ListDetail";
import ListrLists from "./pages/listr/Lists";
import ListrProducten from "./pages/listr/Producten";
import ListrRecipeDetail from "./pages/listr/RecipeDetail";
import ListrRecipes from "./pages/listr/Recipes";
import ListrWeekplanner from "./pages/listr/Weekplanner";
import GardnrBottomNav from "./components/gardnr/GardnrBottomNav";
import KitBottomNav from "./components/ui/KitBottomNav";
import GardnrAreaMap from "./pages/gardnr/AreaMap";
import GardnrAreas from "./pages/gardnr/Areas";
import GardnrPlants from "./pages/gardnr/Plants";
import GardnrToday from "./pages/gardnr/Today";
import GriprAccounts from "./pages/gripr/Accounts";
import GriprBudget from "./pages/gripr/Budget";
import GriprOverview from "./pages/gripr/Overview";
import GriprRecurring from "./pages/gripr/Recurring";
import GriprTransactions from "./pages/gripr/Transactions";

const navLinkClass = (isActive: boolean) =>
  `shrink-0 whitespace-nowrap px-3 py-2 text-sm font-medium rounded-md transition-colors ${
    isActive ? "nav-active" : "text-slate-600 hover:bg-slate-200"
  }`;

export default function App() {
  const pathname = useLocation().pathname;
  const active = activeModule(pathname);
  const inGainr = active.key === "gainr";
  // gardnr's redesign (and every other module, which share its page kit) puts the module switcher
  // in each page's own top row on a phone, so the shared header only shows from tablet width up.
  const inGardnr = active.key === "gardnr";
  const navItems = MODULE_NAV[active.key] ?? [];
  // Drives the per-module accent (see index.css) -- gainr/gripr/listr each get their own
  // header and page-canvas tint, scoped under this class the same way `.dark` scopes dark mode.
  const moduleClass = `module-${active.key}`;
  useModuleBranding(active.key);

  return (
    <div className={`min-h-screen ${moduleClass}`}>
      <header className="app-header sticky top-0 z-40 hidden border-b border-slate-200 sm:block">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-2">
            <ModuleSwitcher />
            {inGainr && <PortfolioSwitcher />}
          </div>
          {/* Desktop/tablet only -- every module gets a bottom navigation bar below `sm`
              instead (the page kit's bar; gardnr's adds an overdue count). */}
          <nav className="hidden gap-1 sm:flex" aria-label="Page sections">
            {navItems.map((item) => {
              const isActive = isNavItemActive(item, pathname);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={isActive ? "page" : undefined}
                  className={navLinkClass(isActive)}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <ModuleIndicators />
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* pb-24 on mobile keeps the last content clear of the fixed bottom nav. */}
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-4 sm:pb-6 sm:pt-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/gripr" element={<GriprAccounts />} />
          {/* Categories merged into Budget -- keep old links and bookmarks working. */}
          <Route path="/gripr/categories" element={<Navigate to="/gripr/budget" replace />} />
          <Route path="/gripr/transactions" element={<GriprTransactions />} />
          <Route path="/gripr/recurring" element={<GriprRecurring />} />
          <Route path="/gripr/budget" element={<GriprBudget />} />
          <Route path="/gripr/overview" element={<GriprOverview />} />
          <Route path="/listr" element={<ListrLists />} />
          <Route path="/listr/lijst/:id" element={<ListrListDetail />} />
          <Route path="/listr/recepten" element={<ListrRecipes />} />
          <Route path="/listr/recept/:id" element={<ListrRecipeDetail />} />
          <Route path="/listr/weekplanner" element={<ListrWeekplanner />} />
          <Route path="/listr/producten" element={<ListrProducten />} />
          <Route path="/listr/voorraad" element={<ListrInventory />} />
          <Route path="/listr/bestellingen" element={<ListrPicnicOrders />} />
          <Route path="/listr/winkelwagen" element={<ListrPicnicCart />} />
          <Route path="/listr/aanbiedingen" element={<ListrPicnicOffers />} />
          <Route path="/gardnr" element={<GardnrAreas />} />
          <Route path="/gardnr/areas/:id" element={<GardnrAreaMap />} />
          <Route path="/gardnr/plants" element={<GardnrPlants />} />
          <Route path="/gardnr/vandaag" element={<GardnrToday />} />
        </Routes>
      </main>

      {inGardnr ? (
        <GardnrBottomNav />
      ) : (
        <KitBottomNav items={navItems} label={`${active.label} sections`} />
      )}
    </div>
  );
}

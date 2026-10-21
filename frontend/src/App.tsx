import { lazy, Suspense } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

import ModuleSwitcher from "./components/ModuleSwitcher";
import PortfolioSwitcher from "./components/PortfolioSwitcher";
import ModuleIndicators from "./components/ModuleIndicators";
import ModuleSettingsButton from "./components/ModuleSettingsButton";
import ThemeToggle from "./components/ThemeToggle";
import { activeModule } from "./config/modules";
import { isNavItemActive, MODULE_NAV } from "./config/moduleNav";
import { useModuleBranding } from "./hooks/useModuleBranding";
import GardnrBottomNav from "./components/gardnr/GardnrBottomNav";
import KitBottomNav from "./components/ui/KitBottomNav";
import { t } from "./i18n";

// Each page is its own chunk, loaded when first visited: one module's pages (and the chart
// library only some of them use) shouldn't be downloaded before any page can show.
const Home = lazy(() => import("./pages/Home"));
const Vandaag = lazy(() => import("./pages/Vandaag"));
const Journal = lazy(() => import("./pages/Journal"));
const Income = lazy(() => import("./pages/Income"));
const Transactions = lazy(() => import("./pages/Transactions"));
const ListrInventory = lazy(() => import("./pages/listr/Inventory"));
const ListrPicnicCart = lazy(() => import("./pages/listr/PicnicCart"));
const ListrPicnicOffers = lazy(() => import("./pages/listr/PicnicOffers"));
const ListrPicnicOrders = lazy(() => import("./pages/listr/PicnicOrders"));
const ListrListDetail = lazy(() => import("./pages/listr/ListDetail"));
const ListrLists = lazy(() => import("./pages/listr/Lists"));
const ListrProducten = lazy(() => import("./pages/listr/Producten"));
const ListrRecipeDetail = lazy(() => import("./pages/listr/RecipeDetail"));
const ListrRecipes = lazy(() => import("./pages/listr/Recipes"));
const ListrWeekplanner = lazy(() => import("./pages/listr/Weekplanner"));
const GardnrAreaMap = lazy(() => import("./pages/gardnr/AreaMap"));
const GardnrAreas = lazy(() => import("./pages/gardnr/Areas"));
const GardnrPlants = lazy(() => import("./pages/gardnr/Plants"));
const GardnrToday = lazy(() => import("./pages/gardnr/Today"));
const GriprAccounts = lazy(() => import("./pages/gripr/Accounts"));
const GriprBudget = lazy(() => import("./pages/gripr/Budget"));
const GriprOverview = lazy(() => import("./pages/gripr/Overview"));
const GriprRecurring = lazy(() => import("./pages/gripr/Recurring"));
const GriprTransactions = lazy(() => import("./pages/gripr/Transactions"));
const TrainrExercises = lazy(() => import("./pages/trainr/Exercises"));
const TrainrHistory = lazy(() => import("./pages/trainr/History"));
const TrainrOverviewPage = lazy(() => import("./pages/trainr/Overview"));
const TrainrPlanner = lazy(() => import("./pages/trainr/Planner"));
const TaskrAgenda = lazy(() => import("./pages/taskr/Agenda"));
const BriefrInbox = lazy(() => import("./pages/briefr/Inbox"));
const NotrNotes = lazy(() => import("./pages/notr/Notes"));
const NotrNotePage = lazy(() => import("./pages/notr/NotePage"));

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
          <nav className="hidden gap-1 sm:flex" aria-label={t("Page sections")}>
            {navItems.map((item) => {
              const isActive = isNavItemActive(item, pathname);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={isActive ? "page" : undefined}
                  className={navLinkClass(isActive)}
                >
                  {t(item.label)}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <ModuleIndicators />
            <ThemeToggle />
            {/* The module's settings gear lives here from tablet width up; on a phone each page's
                top row carries it (ModuleTopRow). */}
            <ModuleSettingsButton />
          </div>
        </div>
      </header>

      {/* pb-24 on mobile keeps the last content clear of the fixed bottom nav. */}
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-4 sm:pb-6 sm:pt-6">
        <Suspense fallback={<div className="py-6 text-center text-sm text-ui-muted">{t("Loading…")}</div>}>
          <Routes>
            <Route path="/" element={<Vandaag />} />
            <Route path="/gainr" element={<Home />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/income" element={<Income />} />
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
            <Route path="/trainr" element={<TrainrPlanner />} />
            <Route path="/trainr/historie" element={<TrainrHistory />} />
            <Route path="/trainr/overzicht" element={<TrainrOverviewPage />} />
            <Route path="/trainr/oefeningen" element={<TrainrExercises />} />
            <Route path="/taskr" element={<TaskrAgenda />} />
            <Route path="/briefr" element={<BriefrInbox />} />
            <Route path="/briefr/archive" element={<BriefrInbox archived />} />
            <Route path="/notr" element={<NotrNotes />} />
            <Route path="/notr/archive" element={<NotrNotes archived />} />
            <Route path="/notr/new" element={<NotrNotePage />} />
            <Route path="/notr/:id" element={<NotrNotePage />} />
          </Routes>
        </Suspense>
      </main>

      {inGardnr ? (
        <GardnrBottomNav />
      ) : (
        // A bar with one tab (taskr) or none (Vandaag) only takes room; those pages are reached
        // from the module switcher and from Vandaag itself.
        navItems.length > 1 && <KitBottomNav items={navItems} label={t("{module} sections", { module: t(active.label) })} />
      )}
    </div>
  );
}

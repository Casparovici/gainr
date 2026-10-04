import { createElement } from "react";
import {
  Baby,
  Banknote,
  Beef,
  Building2,
  Candy,
  Car,
  Carrot,
  Coffee,
  Droplet,
  GlassWater,
  GraduationCap,
  Hammer,
  HandCoins,
  HeartHandshake,
  HeartPulse,
  Home,
  type LucideIcon,
  type LucideProps,
  Landmark,
  Milk,
  MoreHorizontal,
  PiggyBank,
  Plane,
  Repeat,
  Shield,
  Shirt,
  ShoppingBag,
  ShoppingCart,
  Snowflake,
  Soup,
  Sparkles,
  SprayCan,
  Tag,
  Ticket,
  UtensilsCrossed,
  Utensils,
  Wallet,
  Wheat,
} from "lucide-react";

// One icon per top-level category the CSV import preloads (see backend/scripts/import_gripr.py),
// keyed by the exact Dutch name so a category renamed by the user just falls back to the
// generic Tag rather than showing something misleading.
const ICONS: Record<string, LucideIcon> = {
  // expense
  Aankopen: ShoppingBag,
  Abonnementen: Repeat,
  Boodschappen: ShoppingCart,
  Debiteuren: HandCoins,
  "Eten & Drinken": Utensils,
  "Extra Aflossen Hypotheek": PiggyBank,
  "Goede doelen": HeartHandshake,
  Huis: Hammer,
  Kinderen: Baby,
  Kleding: Shirt,
  "Medische kosten": HeartPulse,
  "Persoonlijke verzorging": Sparkles,
  Studieschuld: GraduationCap,
  Vakanties: Plane,
  Vervoer: Car,
  Verzekeringen: Shield,
  "Vrije tijd & Uitjes": Ticket,
  Wonen: Home,
  "Woning Overwaarde": Building2,
  // income
  Belastingdienst: Landmark,
  Salaris: Wallet,
  Toeslagen: Banknote,
  // shared
  Overig: MoreHorizontal,
  // listr (distinct names from gripr's own "Boodschappen" spending category, on purpose)
  "Groente & Fruit": Carrot,
  "Zuivel & Eieren": Milk,
  "Vlees & Vis": Beef,
  "Brood & Bakkerij": Wheat,
  "Pasta, Rijst & Wereldkeuken": UtensilsCrossed,
  "Conserven, Soepen & Sauzen": Soup,
  "Ontbijt & Beleg": Coffee,
  "Snacks & Snoep": Candy,
  Dranken: GlassWater,
  Diepvries: Snowflake,
  "Kruiden, Sauzen & Olie": Droplet,
  "Huishouden & Verzorging": SprayCan,
};

export function categoryIcon(name: string): LucideIcon {
  return ICONS[name] ?? Tag;
}

/** The icon for a category's name, as an element -- a fixed component picked from ICONS, not one
 * made during render, so React keeps it across renders. */
export function CategoryGlyph({ name, ...props }: { name: string } & LucideProps) {
  return createElement(categoryIcon(name), props);
}

/** The app's modules (gainr, gripr, listr, ...). Adding a new one is just a new entry here --
 * the header's module switcher and the per-module accent (`module-<key>` in index.css) both
 * read off this list instead of a hardcoded set of links, so a fourth or fifth module doesn't
 * need its own bespoke wiring. */
export interface ModuleDef {
  key: string;
  label: string;
  path: string;
  matches: (pathname: string) => boolean;
}

export const MODULES: ModuleDef[] = [
  {
    key: "gainr",
    label: "gainr",
    path: "/",
    matches: (p) => !p.startsWith("/gripr") && !p.startsWith("/listr") && !p.startsWith("/gardnr"),
  },
  { key: "gripr", label: "gripr", path: "/gripr", matches: (p) => p.startsWith("/gripr") },
  { key: "listr", label: "listr", path: "/listr", matches: (p) => p.startsWith("/listr") },
  { key: "gardnr", label: "gardnr", path: "/gardnr", matches: (p) => p.startsWith("/gardnr") },
];

export function activeModule(pathname: string): ModuleDef {
  return MODULES.find((m) => m.matches(pathname)) ?? MODULES[0];
}

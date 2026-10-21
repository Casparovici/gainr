/** The app's modules (gainr, gripr, listr, ...). Adding a new one is just a new entry here --
 * the header's module switcher and the per-module accent (`module-<key>` in index.css) both
 * read off this list instead of a hardcoded set of links, so a fourth or fifth module doesn't
 * need its own bespoke wiring. */
export interface ModuleDef {
  key: string;
  label: string;
  path: string;
  matches: (pathname: string) => boolean;
  /** Left out of the module switcher's tiles -- taskr, whose agenda Vandaag shows (and links to). */
  hidden?: boolean;
}

// gainr's own pages carry no prefix but Home's, for the old links' sake.
const GAINR_PAGES = ["/gainr", "/transactions", "/income", "/journal"];

export const MODULES: ModuleDef[] = [
  // The app's start screen (docs/adr/0048): what needs you today, from every module. First, so a
  // path no module claims lands here too.
  { key: "vandaag", label: "Vandaag", path: "/", matches: (p) => p === "/" },
  {
    key: "gainr",
    label: "gainr",
    path: "/gainr",
    matches: (p) => GAINR_PAGES.some((page) => p === page || p.startsWith(`${page}/`)),
  },
  { key: "gripr", label: "gripr", path: "/gripr", matches: (p) => p.startsWith("/gripr") },
  { key: "listr", label: "listr", path: "/listr", matches: (p) => p.startsWith("/listr") },
  { key: "gardnr", label: "gardnr", path: "/gardnr", matches: (p) => p.startsWith("/gardnr") },
  { key: "trainr", label: "trainr", path: "/trainr", matches: (p) => p.startsWith("/trainr") },
  { key: "taskr", label: "taskr", path: "/taskr", matches: (p) => p.startsWith("/taskr"), hidden: true },
  { key: "briefr", label: "briefr", path: "/briefr", matches: (p) => p.startsWith("/briefr") },
  { key: "notr", label: "notr", path: "/notr", matches: (p) => p.startsWith("/notr") },
];

export function activeModule(pathname: string): ModuleDef {
  return MODULES.find((m) => m.matches(pathname)) ?? MODULES[0];
}

/** A gainr holding opened in Home's detail panel -- the deep link journal notes, briefr findings
 * and transactions use. */
export function positionPath(assetId: number): string {
  return `/gainr?position=${assetId}`;
}

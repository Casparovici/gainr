import { useEffect } from "react";

import { isModuleKey } from "../components/ModuleLogo";

/** Points the browser tab at the active module: its logo as the favicon (and home-screen icon)
 * and its name as the title, so a gripr tab and a gainr tab aren't two identical "gainr" tabs.
 * index.html ships gainr's icons as the pre-JS default; this swaps the same <link> elements
 * rather than adding new ones. */
export function useModuleBranding(moduleKey: string) {
  useEffect(() => {
    document.title = moduleKey;
    if (!isModuleKey(moduleKey)) return;
    const set = (selector: string, href: string) => {
      const link = document.querySelector<HTMLLinkElement>(selector);
      if (link) link.href = href;
    };
    set('link[rel="icon"][type="image/svg+xml"]', `/brand/${moduleKey}-icon-small.svg`);
    set('link[rel="icon"][type="image/png"]', `/brand/${moduleKey}-32.png`);
    set('link[rel="apple-touch-icon"]', `/brand/${moduleKey}-192.png`);
  }, [moduleKey]);
}

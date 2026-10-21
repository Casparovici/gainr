import { msg } from "../i18n";
export type FontPackageId = "default" | "a" | "b" | "c";

export interface FontPackage {
  id: FontPackageId;
  label: string;
  /** What it looks like, in a few words. */
  note: string;
  /** The same faces as the `--font-display` / `--font-text` variables in index.css, for the
   * picker's own previews. */
  display: string;
  text: string;
}

export const FONT_PACKAGES: FontPackage[] = [
  { id: "default", label: "Bricolage + Instrument", note: msg("The current look"), display: '"Bricolage Grotesque"', text: '"Instrument Sans"' },
  { id: "a", label: "Manrope + Inter", note: msg("Clean and legible"), display: '"Manrope"', text: '"Inter"' },
  { id: "b", label: "Fraunces + DM Sans", note: msg("Warm and editorial"), display: '"Fraunces"', text: '"DM Sans"' },
  { id: "c", label: "Space Grotesk + IBM Plex Sans", note: msg("Analytical"), display: '"Space Grotesk"', text: '"IBM Plex Sans"' },
];

export const FONT_STORAGE_KEY = "pdt-font";

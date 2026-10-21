// Translations, by direction: what's written in English and its Dutch, and the other way round.
// One file per module keeps each manageable; a source string belongs to exactly one direction.
import { enToNl as briefr } from "./briefr.en";
import { enToNl as gainr } from "./gainr.en";
import { enToNl as gripr } from "./gripr.en";
import { enToNl as notr } from "./notr.en";
import { enToNl as shared } from "./shared.en";
import { nlToEn as gardnr } from "./gardnr.nl";
import { nlToEn as listr } from "./listr.nl";
import { nlToEn as sharedNl } from "./shared.nl";
import { nlToEn as taskr } from "./taskr.nl";
import { nlToEn as trainr } from "./trainr.nl";
import { nlToEn as vandaag } from "./vandaag.nl";

export const NL_FROM_EN: Record<string, string> = { ...shared, ...gainr, ...gripr, ...notr, ...briefr };
export const EN_FROM_NL: Record<string, string> = { ...sharedNl, ...vandaag, ...listr, ...gardnr, ...trainr, ...taskr };

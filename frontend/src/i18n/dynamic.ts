/** Strings the app shows from data rather than from a literal in the code -- gainr's
 * transaction types, gripr's account and transaction kinds, module names -- listed here so the
 * translation check (i18n.test.ts) knows they need a translation. Shown with `t(value)`. */
import { msg } from "./index";

export const DYNAMIC_MESSAGES = [
  // gainr transaction types (api/types.ts TRANSACTION_TYPES)
  msg("Buy"),
  msg("Sell"),
  msg("Dividend"),
  msg("Interest"),
  msg("Deposit"),
  msg("Withdraw"),
  msg("Broker Fee"),
  msg("Staking"),
  msg("Transfer"),
  // Vandaag's own name in the module switcher (config/modules.ts)
  msg("Vandaag"),
];

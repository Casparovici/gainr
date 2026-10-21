import type { ReactNode } from "react";

import PortfolioSwitcher from "./PortfolioSwitcher";
import { ModuleTopRow } from "./ui/kit";

/** A gainr page's top row: the page kit's row, plus the portfolio pill on a phone -- the header
 * that holds the portfolio switcher on wider screens is hidden there. `children` are the page's
 * own actions, after the pill (the settings gear follows from ModuleTopRow); without any, the row
 * is a phone-only one, as the pill is. */
export default function GainrTopRow({ children }: { children?: ReactNode }) {
  return (
    <ModuleTopRow desktop={Boolean(children)}>
      <div className="sm:hidden">
        <PortfolioSwitcher variant="pill" />
      </div>
      {children}
    </ModuleTopRow>
  );
}

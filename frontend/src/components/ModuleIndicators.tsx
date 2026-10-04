import { useLocation } from "react-router-dom";

import { api } from "../api/client";
import { griprApi } from "../api/griprClient";
import NotificationBell from "./NotificationBell";

/** What a module shows next to its switcher -- in the header on a wide screen and in each page's top
 * row on a phone: its notifications bell. listr and gardnr have nothing to report yet. */
export default function ModuleIndicators() {
  const { pathname } = useLocation();
  if (pathname.startsWith("/gripr")) {
    return <NotificationBell storageKey="gripr.notifications.seenAt" queryKey="gripr-notifications" load={griprApi.listNotifications} />;
  }
  if (pathname.startsWith("/listr") || pathname.startsWith("/gardnr")) return null;
  return <NotificationBell storageKey="gainr.notifications.seenAt" queryKey="gainr-notifications" load={api.listNotifications} />;
}

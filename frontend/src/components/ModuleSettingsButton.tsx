import { useLocation } from "react-router-dom";

import { activeModule } from "../config/modules";
import AppSettingsButton from "./AppSettingsButton";
import GainrSettingsButton from "./GainrSettingsButton";
import GriprSettingsButton from "./gripr/GriprSettingsButton";

/** The settings gear at the end of every page's top row: the active module's own settings dialog
 * (gainr's Trading 212 sync, gripr's period and banks), or the app-wide ones for the rest. */
export default function ModuleSettingsButton() {
  const { key } = activeModule(useLocation().pathname);
  if (key === "gainr") return <GainrSettingsButton />;
  if (key === "gripr") return <GriprSettingsButton />;
  return <AppSettingsButton module={key} />;
}

import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme, type Theme } from "../hooks/useTheme";

const OPTIONS: { value: Theme; Icon: typeof Sun; label: string }[] = [
  { value: "light", Icon: Sun, label: "Light" },
  { value: "dark", Icon: Moon, label: "Dark" },
  { value: "system", Icon: Monitor, label: "Follow system" },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-0.5 rounded-md bg-slate-100 p-0.5">
      {OPTIONS.map(({ value, Icon, label }) => (
        <button
          key={value}
          type="button"
          onClick={() => setTheme(value)}
          title={label}
          aria-label={label}
          aria-pressed={theme === value}
          className={`rounded p-1.5 transition-colors ${
            theme === value ? "bg-white text-slate-900 shadow-sm" : "text-slate-400 hover:text-slate-700"
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
        </button>
      ))}
    </div>
  );
}

// The app's one categorical palette, shared by every chart so a colour always means the same
// thing across gainr and gripr. Assigned in fixed order, never cycled or re-sorted by rank —
// beyond these 8 slots, values fold into a single neutral "Other" rather than inventing a 9th
// hue a colourblind reader couldn't tell from an existing one.
export const CATEGORICAL_COLORS = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
];
export const OTHER_COLOR = "#94a3b8"; // neutral slate

// The colour picker's own swatch set (categories, accounts) — a superset of the categorical
// palette plus two neutral greys for a muted category or a "no particular brand colour"
// account. This is a manual, single-entity override, not the automatic categorical assignment
// charts rely on, so it doesn't need to stay colourblind-distinguishable across a whole chart's
// worth of simultaneous series the way CATEGORICAL_COLORS does — never use PICKER_COLORS for
// that. Kept visually distinct from OTHER_COLOR (the "unset" default) so picking grey on
// purpose doesn't look identical to not having picked anything.
export const PICKER_COLORS = [...CATEGORICAL_COLORS, "#64748b", "#334155"]; // + grey, dark grey

// Types for notr's API (backend/app/schemas/notr.py). One note shape serves notr itself, gainr's
// Journal and the Notes sections on a position, a plant and a recipe (docs/adr/0050).

export interface NotrLabel {
  id: number;
  name: string;
  sort_order: number;
  color: string | null;
  is_archived: boolean;
}

/** A gainr position a note is about. */
export interface NotrAsset {
  id: number;
  ticker: string;
  name: string;
}

export interface NotrPlant {
  id: number;
  name: string;
}

export interface NotrRecipe {
  id: number;
  title: string;
}

export interface NotrNote {
  id: number;
  /** May be empty: show the first line of the body instead. */
  title: string;
  /** Markdown. A picture is `![alt](/api/notr/images/<id>)`. */
  body: string;
  pinned: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  /** What the note is about, each ordered by name. All empty for a plain note. */
  assets: NotrAsset[];
  plants: NotrPlant[];
  recipes: NotrRecipe[];
  labels: NotrLabel[];
}

export interface NotrNoteInput {
  title: string;
  body: string;
  pinned?: boolean;
  label_ids?: number[];
  asset_ids?: number[];
  plant_ids?: number[];
  recipe_ids?: number[];
  /** The day the note is about, for one written earlier somewhere else. Create only. */
  created_at?: string;
}

/** On update, omitting a list leaves it alone; `[]` clears it. */
export type NotrNoteUpdate = Partial<Omit<NotrNoteInput, "created_at">> & { is_archived?: boolean };

export interface NotrNoteFilters {
  q?: string;
  labelId?: number;
  assetId?: number;
  plantId?: number;
  recipeId?: number;
  /** gainr's Journal: only notes linked to at least one position. */
  positionsOnly?: boolean;
  archived?: boolean;
}

export interface NotrImage {
  id: number;
  /** What goes in the Markdown. */
  url: string;
  content_type: string;
  size_bytes: number;
}

/** A pinned note, as Vandaag lists it. */
export interface NotrPinnedNote {
  id: number;
  title: string;
  /** The first line of the body, for an untitled note. */
  preview: string;
}

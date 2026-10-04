import { Flower, Flower2, Leaf, LeafyGreen, Sprout, TreeDeciduous, TreePine, Trees, type LucideIcon } from "lucide-react";

import type { GardenPlantIcon, GardenPlantType } from "../../api/gardnrTypes";

export const PLANT_ICON_COMPONENTS: Record<GardenPlantIcon, LucideIcon> = {
  sprout: Sprout,
  tree_deciduous: TreeDeciduous,
  tree_pine: TreePine,
  trees: Trees,
  leaf: Leaf,
  leafy_green: LeafyGreen,
  flower: Flower,
  flower2: Flower2,
};

// A plant with no explicit icon falls back to one derived from its type.
const TYPE_DEFAULT_ICON: Record<GardenPlantType, GardenPlantIcon> = {
  plant: "sprout",
  tree: "tree_deciduous",
  shrub: "trees",
  other: "leaf",
};

export function resolvePlantIcon(icon: GardenPlantIcon | null, type: GardenPlantType): GardenPlantIcon {
  return icon ?? TYPE_DEFAULT_ICON[type];
}

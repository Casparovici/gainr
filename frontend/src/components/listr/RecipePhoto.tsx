import { ChefHat } from "lucide-react";

import { listrApi } from "../../api/listrClient";
import type { ListrRecipe } from "../../api/listrTypes";

/** A recipe's photo in a fixed box, or the chef's hat when it has none. The box size and shape
 *  come from `className`; the image always covers it. */
export default function RecipePhoto({
  recipe,
  className,
  alt = "",
}: {
  recipe: Pick<ListrRecipe, "id" | "updated_at" | "has_photo">;
  className: string;
  alt?: string;
}) {
  if (!recipe.has_photo) {
    return (
      <span className={`flex shrink-0 items-center justify-center bg-ui-brand-soft text-ui-brand-strong ${className}`}>
        <ChefHat className="h-1/2 w-1/2" strokeWidth={2} aria-hidden />
      </span>
    );
  }
  return (
    <img
      src={listrApi.recipePhotoUrl(recipe)}
      alt={alt}
      loading="lazy"
      className={`shrink-0 bg-ui-tile object-cover ${className}`}
    />
  );
}

# 0043 — listr: recipe photos

## Status

Accepted

## Context

Recipes were text only. The recipe list and detail page are easier to scan with a picture, and
Mealie, the source of imported recipes (ADR 0022), already has one for most of them.

## Decision

- One photo per recipe, stored inline as `photo` / `photo_content_type` on `grecipe_recipes`, the
  same way gardnr stores care-log photos (ADR 0012 addendum). The whole-database backup
  (ADR 0013) therefore covers it, with no second backup path.
- `photo` is a deferred column: the recipe list never loads the bytes. `has_photo` is derived
  from the content type.
- Every upload is re-encoded as a JPEG capped at 1600 px on its longest side (rotation from EXIF
  baked in), so a phone original never lands in the database as-is.
- `PUT/DELETE/GET /api/listr/recipes/{id}/photo`. The frontend requests the image with
  `?v=<updated_at>`, so a replaced photo is a new URL and the response is cached for a year.
- The Mealie import takes the recipe's picture (`/media/recipes/{id}/images/original.webp`)
  when Mealie has one, replacing the current photo like the rest of an imported recipe. A
  recipe without a Mealie picture keeps its photo, and a picture that can't be fetched or read
  never fails the import.

## Consequences

Each photo adds roughly 100–300 KB to the database and its backups; at a personal cookbook's
size that is small. A later move to files on disk would be an ADR of its own.

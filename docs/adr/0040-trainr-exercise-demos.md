# 40. trainr: how-to demos for exercises, from free-exercise-db

## Status

Accepted

## Context

The guided workout (ADR 0037's runner) steps through a planned gym session set by set. The user
asked for examples of how to perform each exercise, ideally short GIFs or videos, shown while doing
that exercise. trainr has no media of its own, so this means picking an outside source, which makes
it a data-provider decision and needs a column to link an exercise to it.

## Decisions

**Source: [free-exercise-db](https://github.com/yuhonas/free-exercise-db)**, about 870 exercises,
each with a photo of its start and its end position and step-by-step instructions, released under
the Unlicense (public domain). The runner flips between the two photos once a second, which reads
like a short GIF of one rep. Tapping it steps through the photos by hand, and with reduced motion
that's the only way it changes. The instructions sit folded underneath, in English as the source has
them.

**The catalogue is vendored and the photos are pinned to one upstream commit.**
`backend/app/data/trainr_exercise_demos.json` is the upstream `dist/exercises.json`, trimmed to id,
name, equipment, image paths and instructions, without the three entries that have no photos. It
carries its source, licence and commit. `trainr_exercise_demo_provider.py` validates it on load
and builds the photo URLs on jsDelivr at that same commit
(`cdn.jsdelivr.net/gh/yuhonas/free-exercise-db@<commit>/exercises/<id>/<n>.jpg`, served as
immutable with a year's cache). So searching never touches the network, a linked exercise's URL
never changes underneath it, and a phone that has shown a demo once keeps it cached. Refreshing
the catalogue means regenerating the file from a newer commit. The browser loads the photos from
jsDelivr, which is the one new outbound request; the backend makes none.

**An exercise links at most one demo: `trainr_exercises.demo_id`**, a nullable string holding the
catalogue id. It is a link, not a copy: the exercise list resolves it to the demo's name, photo
URLs and steps on every read, and an id that has left the catalogue simply resolves to no demo.
Create and update accept `demo_id` (null unlinks it) and refuse an id that isn't in the catalogue
(422). `GET /api/trainr/exercise-demos?q=` searches by name, ignoring case, punctuation and a
plural "s". Names that match the most words of the query come first, so a typo in one word still
finds the others. Among equal matches the exact name comes first, then names that start with the
query, then the shortest.

**The migration links the seeded suggestions.** All 43 seeded exercises except Burpee have a
catalogue match. Where none is exact, the closest one is used: a barbell back squat links
"Barbell Squat", a dumbbell thruster links the kettlebell thruster. The migration matches by the
seed name or the catalogue's own name, ignoring case and punctuation, so "Push Up" or
"Dumbbell Bicep Curl" still matches. It fills only exercises that have no demo yet, so it never
overwrites one the user picked. Anything else is linked by hand on the Oefeningen page: a picker
opens already searching on the exercise's name.

**In the runner**, a set shows its exercise's demo under the title, and the rest shows the demo
of the set that comes next, without the steps. One "Voorbeeld verbergen" toggle hides demos on
that device (`localStorage`, a per-viewer convenience) for someone who knows the exercises.

## Alternatives considered

- **ExerciseDB** (animated GIFs, about 1,300 exercises): the free hosted API sits behind RapidAPI
  with a key, its open mirror's certificate had expired when checked, and the GIFs aren't openly
  licensed (only the API code is AGPL). Rejected for licensing and reliability.
- **wger's exercise videos**: CC-BY-SA, but only 78 exist, many are 30+ MB HEVC `.MOV` files
  that phones' browsers won't play inline, and coverage of the seeded list is thin.
- **YouTube embeds per exercise**: a full video player for a two-second movement, ads and
  tracking, and hand-picking a link for every exercise. Rejected.
- **Downloading the photos to the server** (as `asset_logos` caches logos): keeps working if
  jsDelivr is down and avoids the outbound request. It would add about 100 MB for the whole
  catalogue, or a fetch-on-link cache with a table, for a home-gym screen that's on Wi-Fi anyway.
  Not now. The provider is the one place to change if that's ever wanted.

## Consequences

- An exercise added by the user has no demo until one is picked; Burpee has none to pick.
- The demos are photos of the start and end position, not video: fine for showing the shape of
  a movement, not for its tempo or the finer points of form.
- The instructions are English while the rest of trainr is Dutch.

# MV-style character generator for Asteria

## Intent and boundaries

The character creator should work like RPG Maker MV's generator: choose a compatible body template, combine aligned visual parts, and inspect the complete output frame sheets before creating a character. Character identity is the saved selection of face, eyes, brows, nose, mouth, hair, clothing, and accessories, not a one-off full-body illustration. A weapon changes the battle attack motion and weapon animation; armor equipment changes stats but does not change the generated appearance. Existing full-sheet starter portraits remain fixed presets, not interchangeable generator parts.

The existing ignored `local_reference/rpg_maker_mv` tree supplies local reference assets. Do not copy it again, alter the originals, or commit them. Preserve the user's uncommitted repo changes and make no commit.

## Source and compatibility model

Use the existing `RPGMakerMVGeneratorCatalog` and `CharacterRecipe`. A recipe declares one body family: Male, Female, or Kid. All chosen parts must resolve to that same family and a compatible generator source set; a source with a missing representation contributes only to the representations it actually has. Do not silently stretch, substitute, or cross-family-composite an incompatible part. The body part is mandatory for a new character. Switching family clears incompatible selected parts and palette entries and selects the corresponding base body, with the UI stating what changed.

The three families share output topology, not identical pixels or proportions: walking `TV` is 144×192 (3 frames × 4 directions at 48×48), damaged `TVD` is 144×48 (3 × 1), side-view `SV` is 576×384 (9 × 6 at 64×64), and face `FG` is 144×144. Preserve per-source compositing order, including category distinctions currently collapsed by the catalog (e.g. eyebrows versus eyes, cloak versus clothing, accessory slots). Palette changes use source color masks and must preserve transparency and frame alignment.

## Composition and output

Extend `CharacterBundleGenerator` to compose four representations: walking, face, damaged, and side-view. Publishing stays atomic: invalid input produces no partial output directory. Add `damaged.png` and representation metadata to the bundle without changing the existing walking/face/side-view contracts used by map placement and runtime. Persist the recipe, family, source-part IDs, and palette in `character.bundle.json`; loading that metadata back into the workspace restores editable choices. Preexisting three-image bundles remain loadable as fixed assets, with no invented damaged frames.

Weapon visuals are not baked into these sheets. Map weapon type to the MV-style thrust/swing/missile attack motion and its separate `Weapons1–3.png` animation frame source. Rendering is tied to the actor's currently equipped weapon definition; absent or unsupported types use a documented empty-hand fallback. Equipping armor has no visual side effect. This feature must not change numeric equipment behavior.

## Editor experience

The MV creator offers Male, Female, and Kid family choices, category/variation browser, and compatible color controls. Each selection immediately re-composes the same recipe. The preview shows all four complete sheets on a checkerboard (face, 3×4 walking, 3×1 damaged, 9×6 side-view) at nearest-neighbor integer scale where space allows, plus a single-frame/animation view for inspection. A preview label displays the sheet dimensions and frame topology; a missing optional representation is explained rather than faked. The existing map-cell placement remains connected to the generated walking sheet.

Do not treat the current six fixed starter character packs as generator templates. The generator may offer a starter recipe only if it consists of real compatible source part IDs; fixed artwork stays a separate preset choice.

## Validation and acceptance

- Unit tests: catalog maps every requested category distinctly, rejects mixed families and invalid dimensions, composes all four transparent grids, round-trips a recipe, and leaves no partial output on failure.
- Editor tests: all three family options appear; family switching removes incompatible selections; choosing a part updates all four full-sheet previews; frame inspection can reach every walking/damaged/side-view cell; missing representation is reported.
- Integration test: generate a character, place it on a map, save/reopen the project, restore its recipe, and verify the visible walking image and generated assets remain resolvable.
- Battle test: changing weapon type changes the requested attack motion and separate weapon frames, while armor change leaves appearance unchanged.
- Native Editor validation on macOS: visually inspect Male, Female, and Kid combinations across all sheets, then save/reopen and play a battle. Record any renderer-only limitations honestly.

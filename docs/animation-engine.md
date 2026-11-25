# Animation engine reference

The approved drawing baseline is commit `5d152ceceddf7f7d373ed0e37c18522838761e0f`. PNG REVEAL, DRAW ENTRANCE, and FULL ILLUSTRATION DRAW share the same contact-driven renderer and the existing calibrated pen hand. The six-scene approval package is available from [GitHub Actions](https://github.com/arztmp/whiteboard-explainer-engine/actions/runs/45664056280/artifacts/15048046152).

## Authoring raster drawing effects

Use `engine.pen_paint.compile_paint(source, src, mode, center, width, start, chrome, *, prefix)`. It returns timeline elements, the absolute end time of the last pen contact, and the drawing audit. See [the six-scene fixture](../scripts/build-draw-test.py) for a complete scene and timeline.

| Parameter | Meaning |
| --- | --- |
| `source`, `src` | Local PNG as a Python `Path`, and its asset URL relative to the Studio public directory. |
| `mode` | `reveal` for contact-driven color, `draw` for outline, detail, and color, or `full` for finer structural and shading paths before color. |
| `center`, `width` | Image center `(x, y)` and display width in scene pixels. The compiler derives the height from the PNG aspect ratio. |
| `start` | Earliest drawing time in absolute timeline seconds. Leave room for the hand to enter and exit. |
| `chrome`, `prefix` | Chromium executable and a unique prefix for the generated timeline IDs. |

The compiler emits a static image with `penPaint: true` and `enter: "none"`. Each linked stroke is a plain scene-coordinate polyline with `paintFor: {imageId, phase}`, where `phase` is `outline`, `detail`, or `color`. Contact starts at `enterAt` and lasts `enterDuration` seconds. Use `hand: true` on the stroke. Configure the timeline hand with `src`, `tip: {x,y}` in sprite pixels, and optional `scale`. Use scene `penTravel` with absolute `start` and `end`, scene-coordinate `from` and `to`, and optional `lift` and `scale`. Leave time between successive strokes for pen-up movement.

The planner can extend the original alpha support to search for routes. Contact filtering evaluates the source alpha at the actual output size and preserves the final raster. The same stroke path drives the hand, ink, and color mask. Geometry and contact analysis run before rendering.

## Other supported features

| Feature | Main authoring parameters |
| --- | --- |
| Handwriting, native SVG, geometry, graphs, and formulas | The handwriting and scientific planners emit actual pen paths. `type: "formula"` with `latex`, position, and size remains available for KaTeX display. |
| Object carrying and dragging | `carry.mode`, `grip`, `from`, `to`, `target`, and six absolute times from `start` to `end`. `handScale` and post-release `after` moves are optional. |
| Background placement | `engine.background.background_push` places an image from right to left. `stage`, `hand_height`, and `inset` are adjustable. The 1920×1080 defaults are a 300 px visible hand and a 150 px inset from the image's left edge. |
| Entrance, exit, and object transformations | `enter`, `enterAt`, `enterDuration`, `exit`, `exitAt`, `exitDuration`, and `moves`. Slide, rotate, grow, and fade support their existing offsets, angles, pivots, or easing parameters. |
| Zoom, scene transitions, and pixel effects | Per-element `zoom` controls `at`, `in`, `hold`, `out`, `scale`, and `origin`. `scene.camera` controls camera position and scale. `transitionIn` controls the scene transition. `scatter` sets timing, tile grid, direction, rotation, and fade for scattering and reassembly. |
| Typography and timing | Text color and optional `inkShadow` can be authored over images. `screenFixed` keeps overlays outside camera zoom. Timeline dimensions, frame rate, audio, music, and SFX are independent of the drawing effects. |

See [timeline types](../studio/src/types.ts) for the full schema and [the refinement fixture](../scripts/build-motor-refinements.py) for background placement, formulas, and zoom examples. The archived strip and timed raster fill use the `allowLegacyRasterEffects` opt-in. Archived MORPH uses `allowMorph`. The legacy raster TRACE planner requires an explicit opt-in; native SVG drawing remains supported.

## Known limitations and approval evidence

- The cleanup reduced 374 strokes to 274. Every retained contact changed at least one pixel. Three contacts in the galaxy and four in the Newton portrait affect only very faint source pixels below the test's 8/255 contrast threshold on white. They were kept to preserve exact color and alpha.
- Fine interior ink, texture, and cross-hatching are inferred from the raster. Some detail appears with the source color instead of as individual ink strokes. The handwritten math glyph set covers the acceptance test; symbols such as ∞, ∂, and ≠ can be displayed with KaTeX.
- The approved six end frames matched their registered sources in color and alpha. Maximum pen-tip error was 0.023 px. No image changed in the 18 sampled pen-up intervals. The [test report](draw-effects.md) describes the comparison method.
- The [Motor acceptance workflow](../.github/workflows/motor-test.yml) runs the Python, TypeScript, browser, and image regressions on `main`. Its `main` path skips both video renders and media packaging.

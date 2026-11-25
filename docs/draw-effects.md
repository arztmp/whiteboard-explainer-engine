# Pen-driven drawing acceptance

- **PNG REVEAL** follows adaptive closed and open paths derived from alpha geometry and local image structure. Only the swept brush opens the original raster.
- **DRAW ENTRANCE** traces significant external edges, then large internal structures, then paints the source through the contact mask. The same mask erases temporary ink locally.
- **FULL ILLUSTRATION DRAW** uses the outline, structural and contact-mask pipeline with higher analysis resolution and longer detail selection. The automatic raster analyzer uses contrast, color gradients and line continuity. It cannot identify the original artist's stroke history. Geometric hatching candidates are inferred from nearby parallel and intersecting straight tracks. Shading identification remains approximate and does not recover every fine raster detail.
- The two missing repository references are Saturn and Apple. The radial clock mechanism and rounded robot are the respective existing test substitutes.
- The previous strip implementation remains available for archival timelines. The new test uses contact masks for every image. Source PNGs and hand coordinates retain their original values.
- The workflow runs previous browser, Python and TypeScript tests before the new browser contact, idle, pixel and media checks. Each scene holds for two seconds after the pen exits. Final visual acceptance belongs to the user.

Source registration uses an independently decoded original PNG in the same raster bounds. The contact test reports all out-of-brush antialiasing changes and rejects channel excursions above 8/255. Pen-up and final source comparisons are exact.

## Contact cleanup

The compiler replays each candidate with the original PNG alpha at the actual output size before assigning timestamps. The dilated analysis support is limited to route generation. A no-op or redundant stroke may be removed, and a small residual may be attached to a neighboring color route, only if replay still produces the previous final raster exactly. The reports list preflight changes on white (8/255 cutoff), strict zero-change counts, removal reasons and an independent before/after comparison of every retained stroke in the renderer. Very faint residual source pixels that cannot be merged without losing exactness are reported separately.

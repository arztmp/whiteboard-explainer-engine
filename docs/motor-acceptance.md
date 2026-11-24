# Motor acceptance

| Feature | Automated | Visual scope |
|---|---|---|
| Open-hand background placement | PASS | Four directions, stable placement and background stacking on the supplied landscapes. |
| Handwriting and typography | PASS | Scientific labels, multi-line handwriting, digits, units and separate sans-serif text. |
| Formula display | PASS | KaTeX with native accessible MathML and visual layout. The AST-based handwritten system is separate. |
| Formula write | PARTIAL | Native pen strokes for arithmetic and the gravity formula with a fraction and scripts. Advanced examples are displayed with KaTeX. |
| Geometry, diagrams and graphs | PASS | Paths for geometric construction, illustrative force arrows, axes and schematic graph traces. The explainer uses illustrative trajectories. |
| PNG TRACE | PARTIAL | Joined and prioritized route candidates from the supplied butterfly. The coverage report distinguishes selected and omitted detail. |
| PNG reveal and full illustration | PARTIAL | Reveal follows the pen. Newton and Webb accumulate local ink and colour; some source details appear through the local colour layer. |
| SVG | PASS | Native primitive and path extraction, with transforms and local fill regions. |
| Draw, slide, rotate, grow, fade | PASS | Distinct entrance scenes. |
| Fade out, zoom, scatter and reassemble | PASS | Object and camera zoom are separate. Reassembly is checked against real Chromium PNG data. |
| Morph | PARTIAL | Matched contour interpolation and colour interpolation. Raster detail correspondence remains outside this implementation. |
| Object motion and layering | PASS | Curved routes, transforms, dynamic layering and release followed by independent movement. |
| Scene transitions | PASS | Adjacent scenes meet without a seam gap. Hand motion stays outside the transition. The new BG arrives after the transition. |
| Audio and timestamps | PASS | Synthetic markers from an external WAV file. |
| Real English narration and 25-minute render | NOT TESTED | No recorded narration or alignment data supplied. Performance extrapolation is linear and comes from the acceptance render. |

KaTeX is distributed under the MIT license. The uploaded PNGs retain their original bytes. S20 and S32 are identical files; the timeline uses S20 as the canonical member of that pair.

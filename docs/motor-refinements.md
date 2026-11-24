# Motor refinements

- The two landscape scenes use a right-to-left drag and bottom-anchored open hand. Its visible alpha bounds determine its 300 px reference height and 150 px horizontal inset on a 1920×1080 canvas. Both values are authoring parameters.
- The landscape text uses transparent layouts with explicit ink colors. A small optional drop shadow improves contrast over the image. The supplied hand sprites retain their original bytes.
- The formula scenes contain real path strokes, including radical, fraction bars, scripts, summation and integration limits. The Chromium report measures at least one sample from every authored formula stroke. KaTeX remains available through the established formula element.
- Object and camera zoom use independent configurable centers and scales. Labels are screen-fixed and the test checks artwork, caption spacing and the return to baseline.
- Raster TRACE and MORPH are disabled by default. Archived regression fixtures explicitly enable them. SVG and colored drawings remain in use.
- The package includes the complete previous browser regression reports, correction report, timelines, decoded frames and media measurements.
- Narration synchronization and a 25-minute render are outside this test.

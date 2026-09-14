# Reference asset provenance

All raster images were extracted from user-supplied reference files. No remote product assets or generated product photos are required at runtime.

| Asset | User reference | Extraction |
|---|---|---|
| washers.jpg | 1006270818.jpg | Full supplied banner |
| clipper.jpg | 1006270819.jpg | Product photo crop |
| slicer.jpg | 1006270819.jpg | Product photo crop |
| logo.jpg | 1006270819.jpg | Header logo crop |
| clipper-detail.jpg | archive/reference-assets/02_1000774680_0015.jpg | Product image crop |
| pots.jpg, pans.jpg, knives.jpg, jars.jpg | archive/reference-assets/03_1000680915_0010.jpg | Product photo crops |

Some cropped reference images are low-resolution and contain remnants of the original photo background. Replace them with original catalog photography during ERPNext integration. The application icon is a simplified vector mark, not a pixel-identical recreation of the supplied HEC logo.

## Video refinement 1.1.0

Recording IDs and timestamps are documented in VIDEO_REVIEW_AR.md. All new raster assets are cropped reference imagery, not generated product photos.

| Assets | Reference | Extraction |
|---|---|---|
| banner-kitchen, banner-electronics, banner-cookware | V1 21.7s, 24.4s, 8.2s | Banner-only crops |
| cat-kitchen/global/electronics/baking/plastic/toys | V1 21.7s | Sidebar image crops |
| cat-glass/ceramic/spices/plasticware/kitchen-tools/metal/honey | V1 21.7s | Subcategory image crops |
| cat-new/fans/screens/irons/personal/small/ovens/washers | V1 0.2s | Loaded subcategory image crops |
| oven, thermos, flask, straightener | V3 6s | Cart photo crops |
| hec-product | V3 22.5s | Logo-only product image crop, excluding the contact strip |
| banner-discount | V4 2.7s | Kitchen promotion crop |
| tray, banner-grooming | V4 38s | Product/promotion crops |
| affiliate-art | V4 39.2s | Illustration crop; surrounding affiliate banner rebuilt with HTML/CSS and Arabic text because a floating button covers part of the source |

No raw video, credential-entry screenshot, or customer address screenshot is included in the app/source delivery. `screenshots/` contains only native screenshots of the implemented demo.

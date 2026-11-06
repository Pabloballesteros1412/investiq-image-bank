# How to grade the bank's photos

Context: InvestIQ makes Instagram/LinkedIn carousels about investing. Each slide is 4:5 (1200x1500) with the
photo full-bleed and a headline over it. Each tile on a sheet shows exactly the part of the photo a 4:5 slide
would show, the subject's name (bold: a company, a market topic like "Gold" or "Fed", or a GICS sector) and the
photo's own title from Wikimedia Commons. We want to keep only the BEST photos.

Grades:
- 3 BEST: a photo a professional finance account would be happy to post. It clearly shows something that
  belongs to the subject: for a company, its headquarters or a landmark building of its own (ideally with the
  name/logo visible), its store/branch/restaurant with the brand visible, its product, its plane/ship/truck/train
  in livery, its factory/refinery/rig/data center, or a sharp, well-lit portrait of its executive; for a topic or
  sector, a strong, unambiguous image of that idea. AND it is a good photograph in the 4:5 crop: sharp, well
  exposed, level, clean composition, subject not cut off, not cluttered, not a casual snapshot.
- 2 USABLE BUT PLAIN: right subject but dull or flawed: an ordinary office facade with no visible name, grey
  flat light, clutter, awkward crop, an amateur product snapshot, a trade-show booth; or a nice photo only loosely
  tied to the subject.
- 1 REJECT: wrong or doubtful subject (something that only shares the name: a missile called "3M", an old
  plane, a town called Blackstone, a building named after a family; or another company's brand), random streets,
  parking garages, construction fencing, graves, museum displays and posters, documents, boxes and paperwork,
  screens, meetings/press events with politicians, people who are not the subject's executive, children as the
  main subject, maps/charts/drawings, old or historic snapshots (unless the subject is historic, e.g. "1929 crash"),
  poor photos (blurry, dark, tilted, tiny subject, heavily cut by the 4:5 frame), anything you would not want next
  to a stock-market headline.

- Topics and sectors (generic photos, also from Unsplash/Pexels): a company's brand front and centre (an Exxon
  or Shell price sign, Disney's castle, a branded tanker truck) is at most 2, since the chat must never present
  a generic photo as one company's; so is the same scene already used for another subject (one power plant, shot
  twice by the same photographer, turned up in energy and utilities).

Be strict. When unsure between 3 and 2, give 2; between 2 and 1, give 1. Expect roughly 10-25% of tiles to be 3.

Calibration, sheet-001 (3M, A. O. Smith, AB InBev, Abbott):
- 3: tiles 1 and 2 (3M's headquarters tower with the 3M logo, clean sky), 11 (A. O. Smith tech center at dusk
  with the logo lit), 23 (Abbott's CEO on stage, sharp).
- 2: 3 (3M building, no name visible), 5 (worker unloading 3M boxes), 12 (crowded trade-show booth), 14 (plain
  building with logo flag), 15 (AB InBev sign on a lawn), 17-18 (Labatt brewery buildings, plain), 20-21 (beer
  bottle/glass snapshots in bars), 25 (Abbott test device in use), 26 (Abbott logo on an office wall), 30 (grey
  factory gate).
- 1: 4 (office room), 6 (vice president in a meeting), 7 (board game), 8 (1920s Fokker plane: not 3M), 9 (Russian
  missile "3M-54": not 3M), 10 (museum poster), 13 (a grave), 16 (flower bed at SeaWorld), 19 (another
  company's former CEO), 22 (competitor's beer), 24, 27, 28, 29 (test kits, boxes, pill bottles, packaging).

Output: one JSON object, sheet name -> {"3": [tile numbers], "2": [tile numbers]}. Tiles you do not list are 1.
Example: {"sheet-002": {"3": [4, 17], "2": [1, 2, 9, 30]}, "sheet-003": {"3": [], "2": [5]}}

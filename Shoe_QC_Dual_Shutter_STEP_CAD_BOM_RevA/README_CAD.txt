SHOEVISION QC DUAL VERTICAL SLIDING SHUTTER - CONCEPT REV A
==============================================================

UNIT: mm. ORIGIN: center of box in X,Y; bottom surface at Z=0.
BOX SHELL: 800(X) x 520(Y) x 560(Z).
TWO OPPOSING DOORS: X-negative and X-positive END WALLS, parallel YZ planes.
OPENING EACH: Y = -190 to 190; Z = 145 to 455.
DOOR CLOSED: Y -215..215; Z = 120..480; thickness 4.
DOOR STROKE: +350 mm Z; when opened, Z = 470..830.
RAIL TOWERS: approximately 880 mm; assembly total ~890 mm high.

FILES
- step/P01...P13.step: canonical local part models (and P10R rod).
- step/GA_ASSEMBLY_CLOSED.step: complete static reference assembly.
- step/GA_ASSEMBLY_L_OPEN.step: left door raised 350 mm, right closed.
- step/GA_ASSEMBLY_R_OPEN.step: right door raised 350 mm, left closed.
- model_spec.json: parameter, part, and placement manifest.
- BOM.csv: quantities and nominal dimensional references.
- make_cad.py: CADQuery source generating the solids, placements, and STEP.

SolidWorks: File > Open > STEP; import each as part, then rebuild feature-based
SLDPRTs for editability if desired. STEP carries solid geometry, NOT native
SolidWorks mates/feature trees. Slider Mate and motion timing must be created.

IMPORTANT: This is a PRELIMINARY CONCEPT, NOT RELEASED MANUFACTURING DRAWING.
P07/P08/P10/P10R geometries are indicative generic envelopes, NOT validated
parts from real vendors. Actual rail, block, actuator, loads, seals, safety
interlocks, power-off anti-drop protections and tolerance stacks must be
engineered before physical manufacturing.

A robot entering through an OPEN door prevents fully light-tight operation.
Evaluate ambient light rejection, baffles and camera/LED timing accordingly.

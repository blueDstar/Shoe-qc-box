# CAD inspection — Hilykan Rev A

Source geometry is read-only.
Main: `GA_ASSEMBLY_CLOSED.step` · unit: mm · instances: 48

Measured assembly envelope: [954.0, 572.0, 890.0] mm. Includes towers and drive hardware.

| File | Kind | Instances | Measured X/Y/Z mm | Readable |
|---|---|---:|---|---|
| GA_ASSEMBLY_CLOSED.SLDASM | native_reference | — | — | native |
| GA_ASSEMBLY_CLOSED.step | assembly_state | 48 | [954.0, 572.0, 890.0] | True |
| GA_ASSEMBLY_L_OPEN.step | assembly_state | 48 | [954.0, 572.0, 890.0] | True |
| GA_ASSEMBLY_R_OPEN.step | assembly_state | 48 | [954.0, 572.0, 890.0] | True |
| P01.step | part | 1 | [800.0, 520.0, 3.0] | True |
| P02.step | part | 1 | [800.0, 520.0, 3.0] | True |
| P03.step | part | 1 | [800.0, 3.0, 554.0] | True |
| P04.step | part | 1 | [3.0, 520.0, 554.0] | True |
| P05.step | part | 1 | [4.0, 430.0, 360.0] | True |
| P06.step | part | 1 | [30.0, 30.0, 880.0] | True |
| P07.step | part | 1 | [8.0, 12.0, 820.0] | True |
| P08.step | part | 1 | [18.0, 28.0, 38.0] | True |
| P09.step | part | 1 | [62.0, 42.0, 37.0] | True |
| P10.step | part | 1 | [38.0, 38.0, 308.0] | True |
| P10R.step | part | 1 | [12.0, 12.0, 75.0] | True |
| P11.step | part | 1 | [48.0, 108.0, 6.0] | True |
| P12.step | part | 1 | [3.0, 20.0, 360.0] | True |
| P13.step | part | 1 | [30.0, 500.0, 30.0] | True |

## BOM

- P01: BOM 1 / STEP 1 / matched True
- P02: BOM 1 / STEP 1 / matched True
- P03: BOM 2 / STEP 2 / matched True
- P04: BOM 2 / STEP 2 / matched True
- P05: BOM 2 / STEP 2 / matched True
- P06: BOM 4 / STEP 4 / matched True
- P07: BOM 4 / STEP 4 / matched True
- P08: BOM 8 / STEP 8 / matched True
- P09: BOM 8 / STEP 8 / matched True
- P10: BOM 2 / STEP 2 / matched True
- P10R: BOM 2 / STEP 2 / matched True
- P11: BOM 2 / STEP 2 / matched True
- P12: BOM 8 / STEP 8 / matched True
- P13: BOM 2 / STEP 2 / matched True

## Alternate states

- GA_ASSEMBLY_L_OPEN.step: 11 changed instances; deltas recorded in JSON.
- GA_ASSEMBLY_R_OPEN.step: 11 changed instances; deltas recorded in JSON.

## Data limitations

- Rev A source identifies rails, blocks and actuator as generic envelopes, not vendor-validated mechanisms.
- Measured OPEN rod is 425 mm vs CLOSED 75 mm; fixed lower end Z=363 mm. Source make_cad.py differs from actual STEP. Parametric rod display uses measured STEP endpoints.
- No robot or sensor CAD is present. All robot/gripper/shoe and sensor zones are DEMO overlays.

## Measured reference checks

Opening is measured from the rectangular inner wire of P04, not substituted from the source JSON.

- box_mm: measured [800.0, 520.0, 560.0]; reference [800, 520, 560]; matched True
- opening_yz_mm: measured [380.0, 310.0]; reference [380, 310]; matched True
- door_xyz_mm: measured [4.0, 430.0, 360.0]; reference [4, 430, 360]; matched True
- rail_length_mm: measured 820.0; reference 820; matched True
- tower_length_mm: measured 880.0; reference 880; matched True
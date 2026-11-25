# Checks

Each check takes its demand from the FEM and its capacity from the code
formula. The editions are chosen in **Project › Codes**:

- **AISC 360-22 / ACI 318-19** (current).
- **DG1 2nd ed.**: AISC 360-05 and ACI 318-08 as applied by Design Guide 1, to
  reproduce its examples.

| Component | Check |
|---|---|
| Concrete | Bearing with the block centred on the FEM resultant (J8) |
| Plate | Plastic strain (configurable limit, 5 %) and bending from anchor tension |
| Anchors | Steel in tension and shear, pullout, side-face blowout |
| Anchors | Tension, shear and bending with welded washer (AISC J3.7/J3.8) |
| Concrete | Breakout in tension and shear, pryout, interaction |
| Pedestal | Anchor reinforcement in tension (bars and U hairpins) and shear, axial force and bending, minimum steel |
| Shear | Friction, or shear lug (bearing, steel and weld) |
| Weld | Column-to-plate and stiffeners, with directional increase (J2.4) |
| Stiffeners | Plastic strain and slenderness of the free edge |

A row marked *Not governing* is an alternative that does not govern: for
instance concrete breakout when the anchor reinforcement of the pedestal works.

The concrete (ACI) checks are strength-level and are evaluated only for LRFD
combinations.

With the current edition the report adds the analytical path of OpenConex
(rigid plate and stress block) under the same loads, for comparison.

## Recommendations

When a check does not pass, selecting it in the Checks tab shows a list of possible
changes to the adjustable data: anchor diameter or grade, embedment hef, plate
thickness and size, fillet size, anchor reinforcement, pedestal, shear lug. Where a
direct formula exists the minimum value is given (for instance the plate thickness
from tp·√ratio, rounded up to 1/16 in. or 1 mm). The report includes the same list
after the checks table.

They are estimates for one change at a time: the finite element model
redistributes the forces, so solve again after changing the data.

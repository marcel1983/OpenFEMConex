# Validation and limitations

## Examples of Design Guide 1 (2nd ed.)

| Example | Guide | OpenFEMConex |
|---|---|---|
| 4.7 large moment: anchor tension | 76.0 kips | 76.7 kips (FEM) |
| 4.5 uplift: force per anchor | 17.5 kips | 17.5 kips (FEM) |
| 4.5: anchor, breakout and plate ratios | 0.89, 0.90, 0.69 | 0.89, 0.90, 0.69 |
| 4.11: tension, shear and bending of a 1⅛ in. rod | 46.7 > 25.1 ksi | 46.7 > 25.1 ksi |

The capacities of Examples 4.3, 4.5, 4.7 and 4.10 and Table 3.2 are reproduced
by the automatic tests.

## Limitations

- The concrete is elastic: it neither crushes nor cracks. The peak pressure of
  the model is an indicator, not the design demand.
- The anchors are springs: no concrete cone and no local rod bending in the
  model (rod bending is checked with the formula of the guide).
- No fillet radii in W shapes and no rounded corners in HSS.
- Stiffeners only for W shapes and round tubes.
- No seismic design and no ASD check of the concrete.

**Notice:** a support tool. The design is the responsibility of the engineer
who signs it.

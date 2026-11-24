# Quick start

OpenFEMConex designs and checks column base plates with a finite element model
solved in CalculiX, and runs the AISC 360 and ACI 318 checks with the forces
that model gives.

## First calculation

1. **Project › Open** and choose an example from the `examples` folder, for
   instance `dg1_2ed_ej_4_7.ocnx` (Example 4.7 of Design Guide 1).
2. In **Geometry** review the column, plate, anchors, concrete and weld. The
   3D model updates as each value is confirmed.
3. In **Loads** review the cases and tick the combinations to solve.
4. In **Analysis** press **Solve**. CalculiX runs in the background; progress
   shows in the status bar and the details in the *Solver log*.
5. In **Checks** see the table of results. Selecting a row shows its
   calculation trace with the formula and the clause.
6. In **Report** generate the HTML report (with figures) or export it to PDF.

## The window

- **Ribbon** on top: one tab per stage, in working order.
- **Project** on the left: a tree that also works for navigation.
- **3D view** in the centre: model, mesh or results.
- **Properties** on the right: the data of the selected item.
- **Results** at the bottom: solver log and table of checks.

The status bar says whether the data are valid, whether the results are out of
date after a change, and which check governs.

## Data and units

Type every value with its unit: `22 in`, `560 mm`, `376 kip`, `4 ksi`. A bare
number is read in the project units. The units used to show results are chosen
in **Project › Display units**.

Results are saved next to the project, in the `<name>_fem` folder. A
combination that did not change is not solved again.

## Language and theme

**Project › Appearance** sets the language (Spanish or English) and the light
or dark theme. The language applies when the window restarts.

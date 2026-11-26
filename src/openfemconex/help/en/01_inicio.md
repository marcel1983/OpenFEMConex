# Quick start

OpenFEMConex designs and checks column base plates with a finite element model
solved in CalculiX, and runs the AISC 360 and ACI 318 checks with the forces
that model gives.

## First calculation

1. **Project › Open** and choose an example from the `examples` folder, for
   instance `dg1_2ed_ej_4_7.ocnx` (Example 4.7 of Design Guide 1).
2. In **Geometry** review the column, plate, anchors, concrete and weld. The 3D
   model updates when each value is confirmed and shows the dimensions of the
   plate, the anchor layout, the distance f and hef (and the number of each anchor when they are
   at coordinates). Above the view: **＋** and **－** zoom in and out, **Fit**
   brings the whole model back, and the isometric, plan, front and side views;
   the **Dimensions** and **Anchor numbers** boxes show or hide them. The report
   includes a plan view with the dimensions.
3. In **Loads** review the cases and tick the combinations to solve.
   **Edit combinations** defines your own combinations with their factors (one
   per case; negative reverses the case) or copies the ASCE 7 ones so that you
   can change them and untick the generated ones.
4. In **Analysis** press **Solve**. CalculiX runs in the background and a
   floating window shows the combination, the stage, every load increment (with
   its iterations and residual), the time and a progress bar; **Cancel** stops
   CalculiX. **Hide** closes it without stopping the analysis (progress stays in
   the status bar and **Progress** opens it again).
5. In **Checks** see the table of results. Selecting a row shows its
   calculation trace with the formula and the clause.
6. In **Report** generate the HTML report (with figures) or export it to PDF or
   Word (editable .docx). **Report › Title block** keeps the project, number,
   client, connection name, engineer, revision and date that head the report.
   After the isometric views come the dimensioned plan and elevation, with
   callouts for every element and its material and arrows to the welds (fillet
   or CJP).

## Units

The units are chosen in **Project › Display units** and apply everywhere:
forms, tables, dimensions, reports and Word. Every length is in mm (SI and MKS
systems) or in inches (US), the plate and pedestal sizes too. Changing the system
rewrites the values of the project in the new units. A number typed without a
unit is taken in the project units; it can also be typed with its unit
(`22 in`, `560 mm`, `3/4 in`).

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

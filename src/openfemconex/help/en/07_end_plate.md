# Moment end plate

A steel beam welded to an **end plate** that is bolted to the **flange of a
steel column** (strong axis). The connection carries the moment, shear and axial
force of the beam. The analytic checks are those of the OpenConex engine
(`openconex.connections.moment`), which OpenFEMConex calls with the project data
(`openfemconex.end_plate_project`). The CalculiX model and the moment-rotation
curve are added on top of these results.

Standards: AISC 360-22; plate strength and bolt forces after AISC Design Guide
16 and Design Guide 4 (8ES); seismic design after AISC 358-22 Chapter 6 with
AISC 341-22. The sketches of this topic are the program's own drawings.

## Layouts

![End-plate layouts](img/en/placa_extremo_configuraciones.png)

| Layout | Bolt rows per flange | Stiffener | Seismic (AISC 358) |
|---|---|---|---|
| Flush, 1 row | 1 inside | No | No |
| Flush, 2 rows | 2 inside | Optional, between or inside the rows | No |
| Extended 4E | 1 outside and 1 inside | No | Yes (BUEEP) |
| Extended 4ES | 1 outside and 1 inside | On the extension | Yes (BSEEP) |
| Extended multiple row 1/2 and 1/3 | 1 outside and 2 or 3 inside | 1/3 optional | No |
| Extended 8ES | 2 outside and 2 inside | On the extension | Yes (BSEEP) |

All have two bolts per row at the gage g. The program asks for p<sub>f,i</sub>
(inner face of the flange to the first inner row), p<sub>f,o</sub> (outer face of
the flange to the outer row), p<sub>b</sub> (pitch between rows) and the plate
extension past the flange. With a **symmetric** plate the pattern repeats at both
flanges (moment reversal).

## Load path

![Load path](img/en/placa_extremo_fuerzas.png)

- The moment becomes a couple at the flanges, d − t<sub>f</sub> apart:
  **F<sub>fu</sub> = M / (d − t<sub>f</sub>)**. The beam axial force becomes an
  equivalent moment that is added.
- At the tension flange the plate bends between the bolt rows and pulls the
  bolts. The compression flange bears the plate against the column flange.
- The shear is carried by the bolts on the compression side, which are not in
  tension.
- Both flange forces reach the column web, and the panel zone between them works
  in shear.

## Thick or thin plate

![Prying action](img/en/placa_extremo_palanca.png)

A **thick** plate does not yield before the bolts, and each bolt carries its
share of the flange force. A **thin** plate bears at its edge against the column
and the prying force Q adds tension to the bolts. The program classifies the
plate as Design Guide 16 does and checks:

- plate yielding by yield lines, φM<sub>pl</sub>;
- bolt rupture without prying (thick plate) or with prying (thin plate);
- shear of the extension (yielding and rupture, §J4.2);
- shear, bearing and tearout of the compression-side bolts (§J3.7, §J3.11);
- the web welds (shear, and tension near the bolts) and the flange welds
  (§J2.4).

## Column side

![Column limit states](img/en/placa_extremo_columna.png)

1. **Flange bending** of the column around the tension bolts, with its own
   yield-line mechanism (Design Guide 4).
2. **Web local yielding** at the tension flange (§J10.2).
3. **Web crippling** and **buckling** at the compression flange (§J10.3;
   §J10.5 when beams frame into both flanges).
4. **Panel zone** shear (§J10.6), with the doubler plate if any. It needs the
   story shear and the column axial force of each load case.
5. **Continuity plates**: when the column falls short, the plates carry the
   difference and their size and welds are checked (§J10.8 and Design Guide 13).

With continuity plates, the web checks do not apply and the flange bending uses
the stiffened mechanism.

## Seismic design

The 4E (BUEEP), 4ES and 8ES (BSEEP) plates are prequalified for special (SMF)
and intermediate (IMF) moment frames. With seismic design on, the program does
the capacity design: probable beam moment at the hinge, its shear with the
gravity load, moment at the column face, prequalification limits of shapes,
plate and bolts, high or moderate ductility slenderness, column-beam ratio,
panel zone and continuity plates. This block does not depend on the combinations
(it is LRFD) and is shown in the report as "AISC 358". It needs the clear span
of the beam between column faces and, for the column-beam ratio, the column
axial force.

## Loads and report

Load cases give, at the column face: V, M and P of the beam (P positive in
compression) and, when the panel zone is checked, Vc and Pc of the column.
Combinations are generated with ASCE 7 in LRFD or ASD, or typed by hand.

The report follows the common order: data and loads, the checks of each
combination with their trace, the seismic block, and at the end the summary,
recommendations, installation requirements and scope.

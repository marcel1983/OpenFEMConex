# Through-bolts in concrete

A beam end plate connected to a **new** concrete wall or column with bolts that
cross it inside sleeves (no bond) and are anchored on a **continuous back
plate** on the far face. There may be another beam on the far side, on the same
bolts.

The checks of this topic are in the `openfemconex.through_bolt` module
(analytic checks and a CalculiX model). It covers one beam
or two opposite beams, with the shear by friction or with grout.

## Load path

For each beam, with its moment M (positive with tension at the top), its shear
V and the lever arm z = d − tf between the flange centres:

- its tension flange pulls the bolts of that group (top or bottom) with
  **T = |M|/z − P/2**, and its compression flange bears on its face with
  **C = T + P** (P positive in compression);
- the bolts of a group carry the larger tension of the two sides,
  **Tb = max(T1, T2)**; the plate of the side that pulls less bears on its face
  with Tb − Ti (with one beam, the back plate gets the whole T);
- so each face has a bearing zone at the top and one at the bottom. What is not
  balanced across the thickness, ΔF, is carried by a diagonal strut and the
  vertical bars, and bends the member with **ΔM = (M1 − M2) + (V1 − V2) h/2**.

## 1. Shear: by friction or with grout

![Shear by friction](img/en/corte_friccion.png)

**Friction.** The shear goes from the end plate to the concrete by friction
under the compression C: φ μ C ≥ Vu, with the limits of Design Guide 1 and a
user-defined μ (0.55 by default). The bolts carry no shear.

- For: simple to build (empty sleeve) and consistent with the unbonded bolt.
- Against: needs compression in every combination; the pretension is lost to
  creep and shrinkage of the concrete, so it is not counted; seismic design
  normally does not rely on friction. ACI 318 §22.9 only adds **permanent**
  compression to friction: the engineer judges whether the compression of each
  combination is acceptable.

![Shear with grout](img/en/corte_grout.png)

**Grout.** The sleeve is grouted over a length ℓg next to the near face; the
bolt bears laterally on the grout. To keep it unbonded, the bolt is wrapped with
a debonding tape or sheath inside the grout. Checks:

- most loaded bolt with the tension of its group, the shear V/n of the more
  loaded side and the bending over the gap g between plate and grout (lever
  g/2), with the reduced tension of AISC J3.7 (as the rod with a welded plate
  washer of Design Guide 1);
- bolt bearing on the grout: V/n ≤ φ 0.85 f'cg d ℓ, with ℓ = min(ℓg, 4d)
  because the pressure concentrates next to the face;
- shear, bearing and tearout at the plate holes with the bolts of the
  compression zone (Design Guides 16 and 4).

- For: does not depend on compression; works with one side loaded, with axial
  tension and in seismic design.
- Against: more demanding construction; without the debonding the bolt is
  bonded and the tension distribution changes.

## 2. Concrete section

![Forces on the concrete](img/en/concreto_fuerzas.png)

| Check | Reference | How |
|---|---|---|
| Bearing under each plate | ACI 318 §22.8 | A1 = core (flange or washers) plus a plate cantilever l with φ Fy tp²/4 = fp l²/2; A2 from the 1:2 frustum within the member |
| Punching of each group | ACI 318 §22.6 | Force not balanced by the other face; b0 at d/2 from the bearing area, cut by the edges of a column (αs = 40 or 20) |
| Bursting behind each plate | §25.9 (analogy), Ch. 23 | T_burst = 0.25 F (1 − a/H), H = a + h, against the bars of both faces within H |

![Far face](img/en/concreto_cara.png)

A flexible continuous back plate only bears near the tension bolts, so A1 is
limited by the plate bending, not by its whole area.

## 3. Flexure of the wall or column

![Strut and tie](img/en/flexion_muro.png)

The two bearing zones are offset: they form a couple that bends the wall or
column.

- **Next to the connection** (strut-and-tie, ACI 318 Ch. 23): diagonal strut
  from the back plate to the compression zone of the end plate, θ =
  arctan(jz/jx); the vertical bars of each face are the tie, F_t = T tan θ,
  within b_eff = b_bp + 2h. Checks: strut (βs = 0.4, or 0.75 with ties crossing
  it), C-C-T nodes (βn = 0.8, βc = √(A2/A1)), tie, its development ℓd past each
  node and the 25° minimum angle.
- **Away from the connection** (§22.2 to §22.4): M + V h/2 is shared above and
  below (half and half by default); the wall strip of width b_eff, or the whole
  column section with its axial force, is checked.

The global design of the wall or column and the joint of a column with beams on
both sides (ACI 318 Ch. 15) belong to the global analysis.

## 4. Opposite connection

![Opposite connection](img/en/conexion_opuesta.png)

With a beam on the far side, the back plate is the end plate of the other beam
and the bolts are shared. Both plates must have the same bolt rows, gage and
diameter, and the beam axes must be at the same height.

| Case | Bolts | Concrete |
|---|---|---|
| A. Balanced (M1 = M2) | Tb = T, not 2T | Compression at the bottom of both faces only: no strut or punching, ΔM ≈ 0 |
| B. Unbalanced | Tb = max(T1, T2) | Plate 2 bears at the top with T1 − T2; ΔM = M1 − M2 |
| C. One side | Tb = T1 | Plate 2 works as the back plate; ΔM = M1 |
| D. Seismic (same sense) | Top and bottom rows in tension | ΔF = T + C; ΔM = M1 + M2 |

Each beam has its end-plate checks (those of beam 2 show "viga 2" in the
combination) and, with friction, its own shear by friction with the compression
on its face. Under seismic loads friction should not be relied on: use grout.

## In the interface

**Project › Add connection › Through-bolts in concrete** adds a connection with
the data of the first example. When it is selected in the tree:

- **Geometry**: beam, end plate, back plate, wall or column, opposite beam and
  shear; the 3D view shows the wall with its vertical and horizontal bars (ties
  in a column), the plates, the bolts and the grout in the sleeves.
- **Loads**: as for the base plate. Service load cases with their type (D, L,
  W, E…) and their forces at the wall face: V, M and P of beam 1 and, with an
  opposite beam, V2, M2 and P2. Their types give the ASCE 7 LRFD combinations
  (the seismic ones when S<sub>DS</sub> is given; ρ and Ω0 optional). **Edit
  combinations** adds your own combinations or copies the generated ones to
  change their factors; the list marks the ones solved with CalculiX. An older
  project, with factored combinations, is converted: each combination becomes a
  case with its own combination of factor 1.
- **Analysis**: **Settings** has the same options as the base plate (mesh size,
  fast mesh, layers, CalculiX threads, plastic strain limit). **Solve** does it
  all: the analytic checks of every combination and the CalculiX model of the
  checked ones, with the progress window (increments, iterations and time) and
  the solver log. **Checks** shows the table and the trace of the selected row.
- **Report**: HTML (with the 3D view and the diagrams of this topic) or PDF.

## CalculiX model

**Analysis › Solve** solves each combination with CalculiX. The end plate
bearing on the face of the wall or column is the same problem as a base plate
on its concrete block, so that model is used:

- the beam and its end plate are elastic-plastic steel solids; the plate bears
  on the concrete through contact (no tension) and, with shear by friction,
  with friction μ;
- the concrete is an elastic block as deep as the wall thickness h, held above
  and below (the wall or column goes on past the connection);
- the back plate is a flexible steel solid bearing on the far face through
  contact (no tension, no friction): with a thin plate the compression gathers
  behind the bolts in tension;
- with an opposite beam, the other beam and its end plate replace the back
  plate, as a mirror image across the wall, and both beams are loaded **at the
  same time** in one model: the unbalanced case (gravity with different spans)
  and the seismic one (both beams rotate the same way, so one plate bears at the
  top while the other bears at the bottom) come from one solution;
- each bolt is a tension-only spring E·A/L, with L = h plus both plate
  thicknesses, since it is unbonded in the sleeve; it joins the nuts on both
  plates; with grout the bolts also take the shear.

Its forces check the most loaded bolt (with prying, J3.6), the plastic strain
of the plate (5 %), bearing with the contact resultant, friction and the flange
and web welds; with a back plate, also its plastic strain and the bearing under
it; with an opposite beam, the same for beam 2 with the results of its face. The
concrete checks (punching, bursting, strut-and-tie, wall
flexure) stay analytic. The 3D view shows the model with the beam vertical (the
base plate axes). **Fast mesh** is on by default: each combination takes a few
minutes.

## Data

| Data | Description |
|---|---|
| Beam and end plate | Shape, bolt layout (Design Guides 16 and 4), thickness, welds |
| Back plate | Width, height, thickness, steel, washer diameter |
| Wall or column | Kind, thickness (along the bolts), column width, f'c, cover, vertical and horizontal bars at each face, distance to the ends, axial force |
| Opposite beam | Shape and end plate with the same bolts; loads V2, M2, P2 |
| Shear | Friction (μ) or grout (length ℓg, grout f'c, gap g) |

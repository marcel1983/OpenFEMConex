# Through-bolts in concrete

A beam end plate connected to a **new** concrete wall or column with bolts that
cross it inside sleeves (no bond) and are anchored on a **continuous back
plate** on the far face. There may be another beam on the far side, on the same
bolts.

The checks of this topic are in the `openfemconex.through_bolt` module. This
first version covers a single beam with the shear taken by friction; the grout
scheme and the opposite connection are described here and are completed in the
next versions.

## Load path

With the beam moment M and the lever arm z = d − tf between the flange centres:

- the bolts at the tension flange carry **T = |M|/z − P/2** to the back plate,
  which bears on the far face of the concrete (no bond: all the tension reaches
  the back plate);
- the end plate bears on the near face at the compression flange with
  **C = T + P** (P positive in compression).

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
a debonding tape or sheath inside the grout. Checks: bolt combined tension and
shear (AISC J3.7), bearing at the plate holes (J3.10), bolt bearing on the grout
(ACI §22.8) and bolt bending if there is a gap.

- For: does not depend on compression; works with one side loaded, with axial
  tension and in seismic design.
- Against: more demanding construction; without the debonding the bolt is
  bonded and the tension distribution changes.

## 2. Concrete section

![Forces on the concrete](img/en/concreto_fuerzas.png)

| Check | Reference | How |
|---|---|---|
| Bearing under each plate | ACI 318 §22.8 | A1 = core (flange or washers) plus a plate cantilever l with φ Fy tp²/4 = fp l²/2; A2 from the 1:2 frustum within the member |
| Punching at the back plate | ACI 318 §22.6 | Force T; b0 at d/2 from the bearing area, cut by the edges of a column (αs = 40 or 20) |
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
and the bolts are shared. Each plate is checked in both roles. The concrete gets
the unbalanced moment ΔM; under seismic loads the moments act in the same sense
and both the top and the bottom rows are in tension.

## Data

| Data | Description |
|---|---|
| Beam and end plate | Shape, bolt layout (Design Guides 16 and 4), thickness, welds |
| Back plate | Width, height, thickness, steel, washer diameter |
| Wall or column | Kind, thickness (along the bolts), column width, f'c, cover, vertical and horizontal bars at each face, distance to the ends, axial force |
| Shear | Friction (μ) or grout |

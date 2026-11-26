# Solution with CalculiX

This section describes what the program does between **Solve** and the results,
and which parameters it sets on its own.

## Solution flow

For every ticked combination:

1. **Pre-check.** The plastic usage of the modelled column is estimated (axial,
   bending and shear with their plastic capacities). Above 1.5 a warning says it
   may not converge; above 2.0 the combination is not solved. A warning is also
   given for shear without compression (no friction).
2. **Mesh.** Built once for all the combinations (see *Automatic mesh*).
3. **Input file.** `NAME.inp` is written in the `*_fem` folder next to the
   project.
4. **Reuse.** If a solution exists and the `.inp` did not change (same data,
   mesh and loads), the saved results are read without solving again.
5. **CalculiX.** `ccx` runs with half of the machine cores (changed in Analysis ›
   Settings). The progress window reads the `.sta` file (increments) and the
   `.cvg` file (iterations and residual). If CalculiX finds distorted elements
   (*nonpositive jacobian*) it is stopped at once.
6. **Retry.** If it did not converge, it is solved again with the softened anchor
   law (see below) and the attempt that got further is kept.
7. **Reading.** Anchor and concrete reactions come from the `.dat`; displacements,
   stresses, PEEQ and contact pressure from the `.frd`. The forces per anchor,
   the weld forces per unit length, the compression resultant and the
   equilibrium error are computed. The `.json` and the `.vtu` for the viewer are
   written.
8. **AISC and ACI checks** with those demands, and recommendations for the ones
   that do not pass.

## Nonlinear analysis

| Parameter | Value |
|---|---|
| Type | Static (`*STATIC`), nonlinear in material and contact; small displacements (no NLGEOM) |
| Method | CalculiX full Newton-Raphson with automatic incrementation |
| Steps | 1: axial compression alone; 2: moments and shears. Without compression, a single step with everything |
| Step 1 | A single increment (1.0) |
| Step 2 (or single) | Initial increment 0.05, largest 0.2, smallest 1·10⁻⁶ (0.02 when the column is at its limit), up to 200 increments |
| Convergence criteria | CalculiX defaults (`*CONTROLS` unchanged) |
| Partial result | If a step does not finish, the last converged increment and the share of load reached are reported |

Applying the compression first makes the whole plate bear and lets the contact
zone shrink gradually with the moment, instead of having to find it in the
first increment.

## Materials

| Part | Law |
|---|---|
| Column, plate, stiffeners | Elastic-plastic with isotropic hardening (`*PLASTIC`). Default bilinear: yield at Fy and slope E/1000 up to εp = 0.15. Changed per steel in Materials |
| Concrete with grout | Linear elastic, Ec = 4700 √f'c, ν = 0.2 |
| Elements | C3D8I hexahedra (incompatible modes, good in bending with few layers) |

## Plate-concrete contact

- Surface to surface (`*CONTACT PAIR`), plate on concrete.
- Linear pressure-overclosure: stiffness K = 10·Ec / 25 mm and residual tension
  σ∞ = 0.05 MPa (the plate can lift off).
- Friction μ (the project one) only with shear and without welded washers;
  stick stiffness K/10. Without shear the contact is frictionless (symmetric
  system, faster convergence).

## Anchors

- Each anchor is a reference node that follows the area-weighted mean of the
  plate nodes under the washer (`*EQUATION`), tied to the ground by springs
  (`SPRING2`).
- **Axial:** tabulated tension-only law, stiffness E·A/L with L = hef + grout +
  tp. In compression 1/1000 of it (with leveling nuts, the same).
- **Softened law (retry):** the stiffness changes in steps of 10 within ±0.005 mm
  around zero, so that Newton does not chatter when an anchor starts to work.
- **Lateral:** only with welded washers (otherwise shear goes by friction): rod
  bending fixed at both ends over grout + tp/2, 12·E·I/L³, between the plate
  bottom and the concrete next to the rod.

## Shear lug and loads

- The lug is a bearing spring between plate and concrete, stiffness Ec × width,
  in the direction of the shear it resists.
- The loads act on a reference node tied to the column top as a rigid body
  (`*RIGID BODY`). The moments are corrected for the shear lever arm: M top =
  M base ∓ V·Lc, so that the given values act at the base.

## Automatic settings

| Item | Automatic value |
|---|---|
| Modelled column length Lc | 2.5 × the largest section dimension |
| Concrete block | The pedestal when given; otherwise the plate scaled to the project A2/A1 (at most 4). Depth = its largest dimension. Fixed base |
| Fine mesh size | The thinner of the column wall and tp, at least 8 mm |
| Next to walls and stiffeners | At most 1.5 × their thickness (avoids distorted elements) |
| Coarse size | 3 × the fine one; along the column, 2 × the fine one growing upwards |
| Layers | 4 through the plate; 10 in the concrete |
| Fast mesh | Fine × 2 (at least 15 mm), 3 plate layers, 8 in the concrete; the first column level is kept. It refines itself if distorted elements come out |
| CalculiX threads | Half of the cores |
| ccx executable | The given one, `$OPENFEMCONEX_CCX`, the system `ccx` or the copy bundled with the installer |
| Weld | The project fillet or the minimum of Table J2.4; CJP when ticked |
| Friction | Project μ (0.55 on grout, 0.7 on concrete per DG1) |

## Files left behind

In the `*_fem` folder, per combination: `.inp` (input), `.sta` and `.cvg`
(progress), `.dat` (reactions), `.frd` (full results, opens in CalculiX
GraphiX), `.json` (summary) and `.vtu` (for ParaView), plus the report and its
figures.

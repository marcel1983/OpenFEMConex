# Finite element model

The model follows the component approach: steel as solids with an
elastic-plastic material, anchors and concrete bearing as components.

| Part | Model |
|---|---|
| Column, plate and stiffeners | C3D8I hexahedra, bilinear steel or the law chosen in Materials |
| Welds | Shared nodes (continuous joint) |
| Concrete with grout | Elastic block, Ec = 4700 √f'c, fixed base |
| Bearing | Surface-to-surface contact, no tension, friction μ |
| Anchors | Tension-only axial spring (EA/L) spread over the washer area |
| Shear in anchors | Only with welded plate washers; otherwise it goes by friction |
| Shear lug | Bearing spring against the concrete |
| Loads | Rigid body at the column top; P, V and M are given at the base |

The axial load is applied first and the moments and shears afterwards.

## Data added by OpenFEMConex

Besides the OpenConex data, the `.ocnx` file can hold:

- **Anchor rows facing the weak axis** (Geometry › Anchors): unticked, the two
  rows are at x = ±f, facing the flanges; ticked, at y = ±f, with the anchors per
  side spread along N.
- **Anchors by coordinates** (Geometry › Anchors): an x, y table from the plate
  centre. x runs along the column depth.
- **Pedestal reinforcement** (Geometry › Pedestal reinforcement): bars, ties and height. It
  needs the pedestal dimensions.
- **Stiffeners** (Geometry › Stiffeners): for W shapes, in line with the web,
  only at the flange edges (edges) or both (web and edges); in line with both webs
  for cruciform columns; for square and rectangular tubes, at the middle of each
  face (web), two per face next to the corners (edges), both, or diagonal at the
  corners (radial: 4, or 8 with one more at the middle of each face); radial for
  round tubes.
- **Column-to-plate weld** (Geometry › Weld): fillet (given size or the minimum
  of Table J2.4) or **complete joint penetration (CJP)**, checked with the base
  metal of the column wall: √(fn² + 3 fv²) ≤ φ Fy t, φ = 0.90 (Table J2.5, J4.1). The 3D view draws the fillet
  bead in yellow (also the stiffener welds) and a CJP weld as a red line with the
  CJP label.

**U hairpins** (same page): inverted U bars over each anchor, one leg on each
side. They count as anchor reinforcement in tension when the legs are within
0.5·hef; their development is checked above the cone (the bend acts as a hook)
and below it (leg length). No pedestal is needed. They are drawn in green.

The pedestal bars end at the top in a 90° hook, a 180° hook or straight (Top
end). 90° and 180° hooks share the development length l_dh (ACI 318-19
§25.4.3); a straight bar needs the longer l_d.

The pedestal reinforcement is drawn inside the concrete (ties taking shear in
orange), but it is not part of the FEM model: it enters only the checks.

A file with these data opens only in OpenFEMConex.

## Columns, built-up sections and materials

**Cruciform column** (Geometry › Column, Type: Cruciform): a main W-shape and a
second I-shape split along its web into two tees, welded to both faces of the main
web. The flanges of the cross shape lie along the y axis and must fit between the
flanges of the main shape (bf2 < d − 2 tf). Both shapes use the column steel. For
cruciform columns the plate bending from the anchors in tension is taken about the
nearest wall, stiffeners go in line with both webs, and the DG1 analytical path
(which assumes a single shape) is not computed.

**Built-up sections** (Geometry › Library › Sections): I-shapes made of three
welded plates (d, bf, tf, tw), with a view of the section and its properties
(A, I, S, Z, r, J). They are saved with the project and appear in the section
lists of the column and of the cross shape. "Copy from catalog" starts from an
AISC shape.

**Materials** (Geometry › Library › Materials): steels of the AISC library and of
the project (Fy, Fu, E and ν) and anchor rod grades (Fu, Fy, Fnt, Fnv). For each
steel you choose the constitutive law of the finite element model, with a preview
of the stress-strain curve:

| Law | Curve |
|---|---|
| Bilinear | Yield at Fy and slope H (E/1000 when empty) up to the ultimate εp |
| Elastic-perfectly plastic | Perfectly plastic at Fy |
| Trilinear | Plateau at Fy up to the hardening εp, then straight to Fu at the ultimate εp |
| Table | (stress, plastic strain) points starting at (Fy, 0) |

The strengths of the AISC materials are fixed; their FEM law can be changed.

## Mesh

The automatic fine size is the thinner of the column wall and the plate. It is
changed in **Analysis › Settings**, together with the layers through the plate
and the CalculiX threads.

**Fast mesh** (check box in Analysis › Settings, or `--fast` on the command
line): still automatic, but with elements about twice the normal size, three
layers in the plate and fewer layers in the concrete. If distorted elements come
out it refines itself. Use it to try out dimensions; the normal mesh is better
for the final report. In the bundled examples it took between a fifth and half of
the time (the cruciform, from 17.5 to 3.8 min per combination); anchor forces and
bearing changed by less than 3 %, the column-to-plate weld came out up to 10 % low
and the plastic strain well below. The report says so in every combination.

While CalculiX solves, the progress window shows every load increment with its
iterations, the increment cutbacks and the residual force, with **Cancel** to stop
it.

## Warnings before solving

- Next to the column walls and the stiffeners the element size is limited to 1.5
  times their thickness, so that a thin tube does not leave distorted elements.
  If one remains, the program says so before calling CalculiX.
- If the column stub cannot carry the loads (shear, or axial force plus bending
  with the moment V·Lc at its top), a warning is given. Above a usage of 2 the
  combination is not solved: the analysis could not converge.
- With uplift and shear, and no lug or welded washers, there is no friction: the
  anchors take the shear after the plate slides in the holes.

## Results

- **von Mises** and **plastic strain** in the steel, with the deformed shape.
- **Contact pressure** under the plate.
- **Displacement**.
- The tension of each anchor is labelled in the view.

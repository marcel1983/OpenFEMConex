# Finite element model

The model follows the component approach: steel as solids with an
elastic-plastic material, anchors and concrete bearing as components.

| Part | Model |
|---|---|
| Column, plate and stiffeners | C3D8I hexahedra, bilinear steel |
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

- **Anchors by coordinates** (Geometry › Anchors): an x, y table from the plate
  centre. x runs along the column depth.
- **Pedestal reinforcement** (Geometry › Pedestal reinforcement): bars, ties and height. It
  needs the pedestal dimensions.
- **Stiffeners** (Geometry › Stiffeners): in line with the web or three per
  flange for W shapes, radial for round tubes.

The pedestal reinforcement is drawn inside the concrete (ties taking shear in
orange), but it is not part of the FEM model: it enters only the checks.

A file with these data opens only in OpenFEMConex.

## Mesh

The automatic fine size is the thinner of the column wall and the plate. It is
changed in **Analysis › Settings**, together with the layers through the plate
and the CalculiX threads.

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

# ADR-012: FreeCAD Parametric CAD with Spreadsheet Configuration

## Status
Accepted

## Context
The robot is fully 3D-printable and intended to evolve (different servo sizes, arm lengths, user modifications) for 10+ years. Hand-edited meshes diverge from reality immediately; URDF written separately from CAD guarantees sim/real mismatch; BOM compiled by hand goes stale.

## Decision
All mechanical design is **parametric FreeCAD**, driven by a single spreadsheet (`cad/freecad/spreadsheets/openj5_params.FCStd`) containing robot-level parameters:

- RobotHeight, TorsoHeight, ArmLength, HeadSize
- ServoModels per joint
- WallThickness, PrintOrientation, Tolerance
- BatteryType, ElectronicsLayout

Everything else is **generated, never hand-drawn twice**:

```
freecadcmd macros/generate_all.py
  → cad/stl_output/            (printable STLs for chosen size)
  → cad/urdf_export/           (URDF/XACRO for ROS 2 / Gazebo)
  → electronics/bom/           (BOM with costs and supplier links)
  → electronics/harness/       (wiring diagrams)
```

The spreadsheet is the single source of truth; changing one parameter regenerates STLs, URDF and BOM consistently.

## Alternatives Considered
1. **Fusion 360 / Onshape** - Rejected: proprietary cloud lock-in conflicts with open source hardware goals (CERN-OHL-S).
2. **OpenSCAD** - Rejected: excellent for code-CAD but weak for assemblies and BOM integration at this scale.
3. **Hand-modeled STLs + separate hand-written URDF** - Rejected: guaranteed divergence between printed parts, simulation model and documentation.

## Consequences
**Positive:**
- Any dimension change propagates everywhere automatically; no stale artifacts.
- Community forks can produce size variants without CAD expertise (edit spreadsheet only).
- URDF always matches physical geometry → Digital Twin fidelity (ADR-010).

**Negative:**
- Requires FreeCAD scripting discipline; parametric models are harder to build initially than direct modeling.
- Generation adds a build step that contributors must run.

## Implementation Notes
- Target FreeCAD ≥ 0.21, headless via `freecadcmd`.
- Not yet implemented - directory `cad/` is part of ROADMAP v0.4.0/v1.0 deliverables; this ADR fixes the approach before any CAD work begins.

## Related ADRs
- ADR-010: Digital Twin Native (URDF feeds Gazebo)
- ADR-008: Configuration-Driven Development (same philosophy applied to mechanics)

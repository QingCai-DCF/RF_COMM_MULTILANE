# P11 fixture requirements

P11 requires two independently documented fixtures:

- Fixed fixture: four TFDU optical axes at 11.25° nominal angular spacing,
  individually labeled and adjustable without exchanging module identity.
- Rotating fixture: one TFDU with a defined optical-axis datum and repeatable
  angular/index datum.

Both fixtures must reference the canonical nominal D200/D600 geometry without
inventing unfrozen dimensions. Drawings must state the datum system, optical
axis height, radial/axial position, angular tolerance, runout, tilt, module
retention, cable strain relief, window/obstruction geometry, and safe
clearance. The future calibration record must bind measured as-built values,
photos, drawing revision, module IDs, and hashes.

The motion assembly must support bounded forward and reverse operation and a
safe zero-speed setup. It needs guarding, an exclusion zone, an independent
emergency stop, controlled power removal, and a procedure that leaves every
TFDU in shutdown. Mechanical guarding does not replace the electrical
`GLOBAL_PERMIT`, TX kill, duty, stuck-high, one-hot, or frame-admission gates.

from pathlib import Path
import math
import pyreadstat

path = Path("data/originals/nhanes/GLU_J.XPT")

if not path.exists():
    raise SystemExit(f"Dataset not found: {path}")

data, metadata = pyreadstat.read_xport(
    str(path),
    usecols=["LBXGLU", "LBDGLUSI"],
    output_format="dict"
)

total = len(data["LBXGLU"])

valid = [
    (float(a), float(b))
    for a, b in zip(data["LBXGLU"], data["LBDGLUSI"])
    if a is not None and b is not None
    and math.isfinite(float(a))
    and math.isfinite(float(b))
]

errors = [
    abs(mmol - mg * 0.05551)
    for mg, mmol in valid
]

tolerance = 0.00050001

print("Total records:", total)
print("Evaluated records:", len(valid))
print("Within rounding tolerance:", sum(e <= tolerance for e in errors))
print("Outside rounding tolerance:", sum(e > tolerance for e in errors))
print("Maximum absolute error:", max(errors) if errors else "N/A")

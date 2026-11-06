from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import math
import pyreadstat

data, _ = pyreadstat.read_xport(
    str(Path("data/originals/nhanes/GLU_J.XPT")),
    usecols=["LBXGLU", "LBDGLUSI"],
    output_format="dict"
)

pairs = [
    (Decimal(str(mg)), Decimal(str(si)))
    for mg, si in zip(data["LBXGLU"], data["LBDGLUSI"])
    if mg is not None and si is not None
    and math.isfinite(float(mg)) and math.isfinite(float(si))
]

def round_sig(x, digits=3):
    if x == 0:
        return x
    step = Decimal("1").scaleb(x.adjusted() - digits + 1)
    return x.quantize(step, rounding=ROUND_HALF_UP)

for places in (1, 2, 3):
    step = Decimal("1").scaleb(-places)
    matches = sum(
        si == (mg * Decimal("0.05551")).quantize(
            step, rounding=ROUND_HALF_UP
        )
        for mg, si in pairs
    )
    print(f"Matches at {places} decimal places: {matches}/{len(pairs)}")

matches_sig = sum(
    si == round_sig(mg * Decimal("0.05551"))
    for mg, si in pairs
)
print(f"Matches at 3 significant figures: {matches_sig}/{len(pairs)}")

print("Examples not matching 3 significant figures:")
shown = 0
for mg, si in pairs:
    predicted = round_sig(mg * Decimal("0.05551"))
    if si != predicted:
        print(f"  mg/dL={mg}, observed={si}, predicted={predicted}")
        shown += 1
        if shown == 8:
            break

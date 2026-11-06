from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json
import math
import pyreadstat

path = Path("data/originals/nhanes/GLU_J.XPT")
if not path.exists():
    raise SystemExit(f"Dataset not found: {path}")

data, _ = pyreadstat.read_xport(
    str(path),
    usecols=["LBXGLU", "LBDGLUSI"],
    output_format="dict"
)

pairs = [
    (Decimal(str(mg)), Decimal(str(si)))
    for mg, si in zip(data["LBXGLU"], data["LBDGLUSI"])
    if mg is not None and si is not None
    and math.isfinite(float(mg)) and math.isfinite(float(si))
]

def round_sig(value: Decimal, digits: int = 3) -> Decimal:
    if value == 0:
        return value
    place = Decimal("1").scaleb(value.adjusted() - digits + 1)
    return value.quantize(place, rounding=ROUND_HALF_UP)

factor = Decimal("0.05551")
counts = {}

for decimal_places in (1, 2, 3):
    unit = Decimal("1").scaleb(-decimal_places)
    counts[f"{decimal_places}_decimal_places"] = sum(
        observed == (mg * factor).quantize(
            unit, rounding=ROUND_HALF_UP
        )
        for mg, observed in pairs
    )

counts["3_significant_figures"] = sum(
    observed == round_sig(mg * factor)
    for mg, observed in pairs
)

result = {
    "dataset_id": "nhanes-2017-2018-glu-j",
    "source_file": path.as_posix(),
    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "conversion_factor": str(factor),
    "records_total": len(data["LBXGLU"]),
    "records_evaluable": len(pairs),
    "rounding_matches": counts,
    "interpretation": (
        "Empirical comparison on the same dataset used to "
        "select rounding; no independent held-out confirmation."
    ),
    "rule_status": (
        "candidate_empirically_supported_not_independently_validated"
    )
}

output = Path("data/evaluation/nhanes-glucose-precision.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

print(json.dumps(result, indent=2))
print(f"Saved: {output}")

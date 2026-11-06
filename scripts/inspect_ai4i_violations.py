import csv
from pathlib import Path
from collections import Counter

path = Path("data/originals/ai4i/ai4i2020.csv")
modes = ["TWF", "HDF", "PWF", "OSF", "RNF"]

violations = []
reverse_mismatches = []
mode_counts = Counter()
patterns = Counter()
total = 0
overall_failures = 0

with path.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)

    for row in reader:
        total += 1
        failure = int(row["Machine failure"])
        overall_failures += failure

        active = tuple(m for m in modes if int(row[m]) == 1)

        if active and failure == 0:
            violations.append(row["UDI"])
            patterns[active] += 1
            mode_counts.update(active)

        if not active and failure == 1:
            reverse_mismatches.append(row["UDI"])

print("Total records:", total)
print("Machine failure = 1:", overall_failures)
print("Forward violations:", len(violations))
print("Reverse mismatches:", len(reverse_mismatches))

print("\nFailure modes among forward violations:")
for mode in modes:
    print(f"  {mode}: {mode_counts[mode]}")

print("\nActive-mode combinations:")
for pattern, count in patterns.most_common():
    print(pattern, count)

print("\nForward violation UDI values:")
print(violations)

print("\nReverse mismatch UDI values:")
print(reverse_mismatches)

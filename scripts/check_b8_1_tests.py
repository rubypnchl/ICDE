"""Run B8.1 unittest cases with stdout-only reporting for Windows PowerShell 5.1."""
from pathlib import Path
import sys
import unittest

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_b8_1_gate_ablation.py')
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

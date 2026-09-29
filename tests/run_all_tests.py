"""Master Automated Test Runner for Arshaf Sanitary Store Management System.
Executes complete test suite including backend API workflows, database logic,
Jinja2 template compilation, and responsive frontend validations.
"""
import sys
import unittest
import glob
import os
import jinja2

def run_all():
    print("=" * 70)
    print("ARSHAF SANITARY STORE — COMPLETE AUTOMATED TEST SUITE")
    print("=" * 70)

    # 1. Template Compilation Check
    print("\n[Phase 1] Jinja2 Template Syntax Validation...")
    tpl_dir = os.path.join(os.path.dirname(__file__), "..", "app", "templates")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(tpl_dir))
    tpl_files = glob.glob(os.path.join(tpl_dir, "**", "*.html"), recursive=True)
    failed_tpls = []
    for f in tpl_files:
        rel = os.path.relpath(f, tpl_dir).replace("\\", "/")
        try:
            env.get_template(rel)
        except Exception as e:
            failed_tpls.append((rel, str(e)))

    if failed_tpls:
        print(f"FAILED: {len(failed_tpls)} template(s) failed syntax compilation:")
        for tpl, err in failed_tpls:
            print(f"  - {tpl}: {err}")
        return 1
    else:
        print(f"SUCCESS: All {len(tpl_files)} Jinja2 templates compiled with 0 syntax errors.")

    # 2. Discover and execute test cases
    print("\n[Phase 2] Executing Full E2E & Responsive Test Suite...")
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.dirname(__file__), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("TEST EXECUTION SUMMARY:")
    print(f"  Total Tests Executed: {result.testsRun}")
    print(f"  Passed:               {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures:             {len(result.failures)}")
    print(f"  Errors:               {len(result.errors)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("ALL TESTS PASSED SUCCESSFULLY! (100% PASS RATE)")
        return 0
    else:
        print("SOME TESTS FAILED.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all())

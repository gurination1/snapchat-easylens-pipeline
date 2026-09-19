#!/usr/bin/env python3
"""
Unified Pre-flight Test Runner for Snapchat Lens Pipeline.
Runs all verification suites:
1. test_js_linter.py (Static JS syntax & Snapchat runtime globals)
2. test_canvas_killer.py (Gate 5 2D canvas API & spinner blocker)
3. test_niche_expansion.py (50-concept archetype matrix & LRU deduplication)
4. test_video_quality_audit.py (Gate 7 FFmpeg black-screen, freeze & motion variance)
5. test_advanced_gates.py (Full Gate 5 & Gate 7 integration suite)
"""
import sys
import unittest
import subprocess

def run_script(script_name):
    print(f"\n{'='*60}\nRUNNING {script_name}...\n{'='*60}")
    res = subprocess.run([sys.executable, script_name], capture_output=False)
    if res.returncode != 0:
        print(f"FAILED: {script_name} exited with code {res.returncode}")
        return False
    return True

def main():
    scripts = [
        "test_js_linter.py",
        "test_canvas_killer.py",
        "test_niche_expansion.py",
        "test_video_quality_audit.py",
        "test_advanced_gates.py",
        "test_multi_model_vfx_parity.py"
    ]
    all_passed = True
    for s in scripts:
        if not run_script(s):
            all_passed = False
            break

    if all_passed:
        print("\n" + "="*60)
        print("ALL PRE-FLIGHT VERIFICATION SUITES PASSED (100% SUCCESS)!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "!"*60)
        print("PRE-FLIGHT VERIFICATION FAILED!")
        print("!"*60)
        sys.exit(1)

if __name__ == "__main__":
    main()

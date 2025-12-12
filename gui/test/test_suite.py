"""
Test Runner for GUI Test Suite

This script provides a convenient interface to run all GUI tests.
Based on backend/test/test_suite.py
"""

import subprocess
import argparse
from pathlib import Path
from typing import List, Optional
from test_definitions import TEST_MODULES


class PyTestRunner:
    """Manages test execution with pytest"""

    def __init__(self, test_dir: str = "tests"):
        self.test_dir = Path(test_dir)
        self.available_modules = self._discover_test_modules()

    def _discover_test_modules(self) -> List[str]:
        """Discover all test modules in the test directory"""
        if not self.test_dir.exists():
            return []

        test_files = list(self.test_dir.glob("test_*.py"))
        return [f.stem for f in test_files]

    def _build_pytest_command(
        self,
        modules: Optional[List[str]] = None,
        test_class: Optional[str] = None,
        test_method: Optional[str] = None,
        verbose: bool = False,
        coverage: bool = False,
        markers: Optional[str] = None,
        failed_first: bool = False,
        maxfail: Optional[int] = None,
    ) -> List[str]:
        """Build pytest command with specified options"""
        cmd = ["pytest"]
        
        # Point to test directory
        target_path = str(self.test_dir)

        if modules:
            for module in modules:
                test_file = TEST_MODULES.get(module, f"test_{module}.py")
                cmd.append(str(self.test_dir / test_file))
        else:
            cmd.append(target_path)

        if test_class:
            cmd.extend(["-k", test_class])
        
        if test_method:
             cmd.extend(["-k", test_method])

        if verbose:
            cmd.append("-v")
        
        if failed_first:
            cmd.append("--ff")
            
        if maxfail:
            cmd.extend(["--maxfail", str(maxfail)])

        return cmd

    def run_tests(self, **kwargs) -> int:
        cmd = self._build_pytest_command(**kwargs)
        print(f"Running command: {' '.join(cmd)}")
        return subprocess.run(cmd).returncode

    def list_modules(self):
        print("Available Modules:")
        for name, file in TEST_MODULES.items():
            print(f"- {name}: {file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GUI Test Runner")
    parser.add_argument("-m", "--module", nargs="+", help="Modules to run")
    parser.add_argument("--list", action="store_true", help="List modules")
    parser.add_argument("-v", "--verbose", action="store_true")
    
    args = parser.parse_args()
    
    # Defaults correctly to current directory for the script execution context
    runner = PyTestRunner(test_dir=str(Path(__file__).parent))
    
    if args.list:
        runner.list_modules()
    else:
        runner.run_tests(modules=args.module, verbose=args.verbose)

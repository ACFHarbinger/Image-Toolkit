"""
Test Runner for ConfigsParser Test Suite

This script provides a convenient interface to run all tests or specific test modules
for the configs_parser testing suite.

Usage:
    # Run all tests
    python run_tests.py
    
    # Run specific test module
    python run_tests.py --module train
    
    # Run multiple modules
    python run_tests.py --module train eval test
    
    # Run with coverage report
    python run_tests.py --coverage
    
    # Run with verbose output
    python run_tests.py --verbose
    
    # Run specific test class
    python run_tests.py --class TestTrainCommand
    
    # Run specific test method
    python run_tests.py --test test_train_default_parameters
    
    # List all available test modules
    python run_tests.py --list
"""
import subprocess
from pathlib import Path
from typing import List, Optional

from .test_definitions import TEST_MODULES


class PyTestRunner:
    """Manages test execution with pytest"""
    def __init__(self, test_dir: str = 'tests'):
        self.test_dir = Path(test_dir)
        self.available_modules = self._discover_test_modules()
    
    def _discover_test_modules(self) -> List[str]:
        """Discover all test modules in the test directory"""
        if not self.test_dir.exists():
            return []
        
        test_files = list(self.test_dir.glob('test_*.py'))
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
        capture: str = 'auto',
        tb_style: str = 'auto',
        parallel: bool = False,
        keyword: Optional[str] = None
    ) -> List[str]:
        """Build pytest command with specified options"""
        cmd = ['pytest']
        
        # Determine test targets
        if test_method:
            # Specific test method (requires module or searches all)
            if modules:
                for module in modules:
                    test_file = TEST_MODULES.get(module, f'test_{module}.py')
                    target = str(self.test_dir / test_file)
                    if test_class:
                        cmd.append(f'{target}::{test_class}::{test_method}')
                    else:
                        cmd.append(f'{target}::-k {test_method}')
            else:
                cmd.append(str(self.test_dir))
                if test_class:
                    cmd.extend(['-k', f'{test_class} and {test_method}'])
                else:
                    cmd.extend(['-k', test_method])
        
        elif test_class:
            # Specific test class
            if modules:
                for module in modules:
                    test_file = TEST_MODULES.get(module, f'test_{module}.py')
                    cmd.append(f'{self.test_dir / test_file}::{test_class}')
            else:
                cmd.append(str(self.test_dir))
                cmd.extend(['-k', test_class])
        
        elif modules:
            # Specific modules
            for module in modules:
                test_file = TEST_MODULES.get(module, f'test_{module}.py')
                cmd.append(str(self.test_dir / test_file))
        
        else:
            # All tests
            cmd.append(str(self.test_dir))
        
        # Add pytest options
        if verbose:
            cmd.append('-v')
        
        if coverage:
            cmd.extend([
                '--cov=configs_parser',
                '--cov-report=html',
                '--cov-report=term-missing'
            ])
        
        if markers:
            cmd.extend(['-m', markers])
        
        if failed_first:
            cmd.append('--ff')
        
        if maxfail:
            cmd.extend(['--maxfail', str(maxfail)])
        
        if capture != 'auto':
            cmd.append(f'--capture={capture}')
        
        if tb_style != 'auto':
            cmd.append(f'--tb={tb_style}')
        
        if parallel:
            # Requires pytest-xdist
            cmd.extend(['-n', 'auto'])
        
        if keyword:
            cmd.extend(['-k', keyword])
        
        return cmd
    
    def run_tests(self, **kwargs) -> int:
        """Execute tests with pytest"""
        cmd = self._build_pytest_command(**kwargs)
        
        print(f"Running command: {' '.join(cmd)}")
        print("=" * 80)
        
        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except FileNotFoundError:
            print("Error: pytest not found. Please install it with: pip install pytest")
            return 1
        except KeyboardInterrupt:
            print("\nTest execution interrupted by user")
            return 130
    
    def list_modules(self) -> None:
        """List all available test modules"""
        print("\n" + "=" * 80)
        print("Available Test Modules:")
        print("=" * 80)
        
        if not self.available_modules:
            print("No test modules found in the test directory.")
            return
        
        # Predefined modules
        print("\nPredefined modules (can use short names):")
        for short_name, filename in sorted(TEST_MODULES.items()):
            status = "✓" if filename.replace('.py', '') in self.available_modules else "✗"
            print(f"  {status} {short_name:15} -> {filename}")
        
        # Discovered modules not in predefined list
        discovered_only = set(self.available_modules) - set(f.replace('.py', '') for f in TEST_MODULES.values())
        if discovered_only:
            print("\nAdditional discovered modules:")
            for module in sorted(discovered_only):
                print(f"  ✓ {module}.py")
        
        print("\n" + "=" * 80)
    
    def list_tests(self, module: Optional[str] = None) -> None:
        """List all tests in a module or all modules"""
        cmd = ['pytest', '--collect-only', '-q']
        
        if module:
            test_file = TEST_MODULES.get(module, f'test_{module}.py')
            cmd.append(str(self.test_dir / test_file))
        else:
            cmd.append(str(self.test_dir))
        
        print(f"Collecting tests...")
        print("=" * 80)
        subprocess.run(cmd)

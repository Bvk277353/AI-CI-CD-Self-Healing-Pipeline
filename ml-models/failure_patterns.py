"""
Failure Pattern Analysis Module
Analyzes and categorizes common CI/CD failure patterns
"""

import re
from typing import Dict, List, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class FailurePatternAnalyzer:
    """Analyze CI/CD failure logs and identify patterns"""
    
    def __init__(self):
        self.patterns = {
            'missing_dependency': [
                r"ModuleNotFoundError: No module named ['\"](\w+)['\"]",
                r"ImportError: cannot import name ['\"](\w+)['\"]",
                r"ERROR: Could not find a version that satisfies the requirement (\S+)",
                r"npm ERR! 404  '(\S+)' is not in the npm registry",
                r"Package ['\"](\w+)['\"] not found"
            ],
            'test_timeout': [
                r"FAILED.*test_(\w+).*Timeout",
                r"pytest\.timeout\.Timeout",
                r"Test exceeded (\d+)s timeout",
                r"TimeoutError"
            ],
            'test_failure': [
                r"AssertionError: (.+)",
                r"FAILED.*test_(\w+)",
                r"Error: Assertion `(.+)` failed",
                r"Expected .+ but got .+"
            ],
            'build_failure': [
                r"Build step.*failed with exit code (\d+)",
                r"ERROR: Build failed",
                r"make: \*\*\* \[.*\] Error (\d+)",
                r"Compilation error"
            ],
            'deployment_crash': [
                r"Deployment.*crashed",
                r"CrashLoopBackOff",
                r"Error: Application failed to start",
                r"Health check failed"
            ],
            'resource_limit': [
                r"OOMKilled",
                r"OutOfMemoryError",
                r"Resource limit exceeded",
                r"Disk space full"
            ],
            'network_timeout': [
                r"Connection refused",
                r"Connection timeout",
                r"dial tcp.*timeout",
                r"Network is unreachable"
            ],
            'syntax_error': [
                r"SyntaxError: (.+)",
                r"IndentationError",
                r"invalid syntax",
                r"unexpected token"
            ],
            'permission_error': [
                r"PermissionError",
                r"Permission denied",
                r"Access denied",
                r"Forbidden"
            ],
            'configuration_error': [
                r"Configuration error",
                r"Invalid configuration",
                r"Missing required.*config",
                r"KeyError: ['\"](\w+)['\"]"
            ]
        }
        
        self.healing_difficulty = {
            'missing_dependency': 'easy',
            'test_timeout': 'easy',
            'test_failure': 'medium',
            'build_failure': 'medium',
            'deployment_crash': 'medium',
            'resource_limit': 'easy',
            'network_timeout': 'easy',
            'syntax_error': 'hard',
            'permission_error': 'hard',
            'configuration_error': 'medium'
        }
    
    def identify_pattern(self, error_log: str) -> Tuple[str, Dict]:
        """Identify failure pattern from error logs"""
        for pattern_type, regex_list in self.patterns.items():
            for regex in regex_list:
                match = re.search(regex, error_log, re.IGNORECASE)
                if match:
                    details = {
                        'pattern_type': pattern_type,
                        'matched_text': match.group(0),
                        'captured_groups': match.groups() if match.groups() else (),
                        'difficulty': self.healing_difficulty.get(pattern_type, 'unknown')
                    }
                    return pattern_type, details
        
        return 'unknown', {'pattern_type': 'unknown', 'difficulty': 'hard'}
    
    def extract_package_name(self, error_log: str) -> str:
        """Extract package name from dependency errors"""
        patterns = [
            r"ModuleNotFoundError: No module named ['\"](\w+)['\"]",
            r"ImportError: cannot import name ['\"](\w+)['\"]",
            r"Could not find a version that satisfies the requirement (\S+)",
            r"npm ERR! 404  '(\S+)' is not in"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_log)
            if match:
                package = match.group(1)
                package = re.sub(r'[<>=!]+.*', '', package)
                return package.strip()
        
        return None
    
    def extract_test_name(self, error_log: str) -> str:
        """Extract test name from test failures"""
        patterns = [
            r"FAILED.*test_(\w+)",
            r"test_(\w+).*FAILED",
            r"Error in test_(\w+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_log)
            if match:
                return f"test_{match.group(1)}"
        
        return "unknown_test"
    
    def is_flaky_test(self, test_history: List[bool]) -> bool:
        """Determine if a test is flaky based on pass/fail history"""
        if len(test_history) < 5:
            return False
        
        failure_rate = test_history.count(False) / len(test_history)
        return 0.20 <= failure_rate <= 0.80
    
    def analyze_batch(self, error_logs: List[str]) -> Dict:
        """Analyze multiple error logs and return statistics"""
        pattern_counts = Counter()
        details_list = []
        
        for log in error_logs:
            pattern_type, details = self.identify_pattern(log)
            pattern_counts[pattern_type] += 1
            details_list.append(details)
        
        total = len(error_logs)
        pattern_stats = {
            pattern: {
                'count': count,
                'percentage': (count / total) * 100,
                'difficulty': self.healing_difficulty.get(pattern, 'unknown')
            }
            for pattern, count in pattern_counts.items()
        }
        
        return {
            'total_failures': total,
            'pattern_distribution': pattern_stats,
            'most_common': pattern_counts.most_common(5),
            'details': details_list
        }
    
    def get_healing_strategy(self, pattern_type: str) -> str:
        """Get recommended healing strategy for a pattern"""
        strategies = {
            'missing_dependency': 'add_to_requirements',
            'test_timeout': 'increase_timeout',
            'test_failure': 'analyze_and_fix',
            'build_failure': 'clear_cache_and_retry',
            'deployment_crash': 'rollback',
            'resource_limit': 'increase_resources',
            'network_timeout': 'add_retry',
            'syntax_error': 'manual_intervention',
            'permission_error': 'manual_intervention',
            'configuration_error': 'validate_config'
        }
        
        return strategies.get(pattern_type, 'manual_intervention')
    
    def estimate_fix_time(self, pattern_type: str) -> int:
        """Estimate time (in seconds) to apply automated fix"""
        fix_times = {
            'missing_dependency': 60,
            'test_timeout': 30,
            'test_failure': 120,
            'build_failure': 90,
            'deployment_crash': 180,
            'resource_limit': 45,
            'network_timeout': 30,
            'syntax_error': 0,
            'permission_error': 0,
            'configuration_error': 60
        }
        
        return fix_times.get(pattern_type, 0)
    
    def can_auto_heal(self, pattern_type: str) -> bool:
        """Check if pattern can be automatically healed"""
        auto_healable = [
            'missing_dependency',
            'test_timeout',
            'build_failure',
            'deployment_crash',
            'resource_limit',
            'network_timeout'
        ]
        
        return pattern_type in auto_healable


# Sample errors for testing
SAMPLE_ERRORS = {
    'missing_dependency': """
Traceback (most recent call last):
  File "app.py", line 3, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
""",
    
    'test_timeout': """
FAILED tests/test_slow.py::test_data_processing - Timeout
Test exceeded 60s timeout
""",
    
    'test_failure': """
FAILED tests/test_api.py::test_user_creation
AssertionError: Expected status code 200 but got 404
""",
    
    'deployment_crash': """
Error: Deployment app-deployment crashed
CrashLoopBackOff: container failed health check
""",
    
    'resource_limit': """
OOMKilled: Container exceeded memory limit (512Mi)
""",
    
    'network_timeout': """
ERROR: Connection timeout when connecting to registry.hub.docker.com
dial tcp 104.26.13.115:443: i/o timeout
"""
}


def demo():
    """Demo the pattern analyzer"""
    analyzer = FailurePatternAnalyzer()
    
    print("=" * 70)
    print("FAILURE PATTERN ANALYZER DEMO")
    print("=" * 70)
    
    for error_type, error_log in SAMPLE_ERRORS.items():
        print(f"\n{error_type.upper().replace('_', ' ')}:")
        print("-" * 70)
        
        pattern_type, details = analyzer.identify_pattern(error_log)
        strategy = analyzer.get_healing_strategy(pattern_type)
        fix_time = analyzer.estimate_fix_time(pattern_type)
        can_heal = analyzer.can_auto_heal(pattern_type)
        
        print(f"Pattern Type: {pattern_type}")
        print(f"Difficulty: {details['difficulty']}")
        print(f"Strategy: {strategy}")
        print(f"Estimated Fix Time: {fix_time}s")
        print(f"Can Auto-Heal: {'✅ Yes' if can_heal else '❌ No'}")
        
        if pattern_type == 'missing_dependency':
            package = analyzer.extract_package_name(error_log)
            print(f"Missing Package: {package}")
    
    print("\n" + "=" * 70)
    print("BATCH ANALYSIS")
    print("=" * 70)
    
    logs = list(SAMPLE_ERRORS.values())
    batch_results = analyzer.analyze_batch(logs)
    
    print(f"Total Failures: {batch_results['total_failures']}")
    print(f"\nPattern Distribution:")
    for pattern, stats in batch_results['pattern_distribution'].items():
        print(f"  {pattern:.<30} {stats['count']:>3} ({stats['percentage']:>5.1f}%)")
    
    print(f"\nMost Common Patterns:")
    for pattern, count in batch_results['most_common']:
        print(f"  {pattern:.<30} {count:>3}")


if __name__ == "__main__":
    demo()
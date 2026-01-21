"""
Codebase Analyzers
==================

Modules for analyzing existing codebases to detect tech stack,
extract features, and prepare for import into Autocoder.

Main entry point: stack_detector.py
"""

from .stack_detector import StackDetector, StackDetectionResult
from .base_analyzer import BaseAnalyzer

__all__ = [
    "StackDetector",
    "StackDetectionResult",
    "BaseAnalyzer",
]

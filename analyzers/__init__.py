"""
Codebase Analyzers
==================

Modules for analyzing existing codebases to detect tech stack,
extract features, and prepare for import into Autocoder.

Main entry points:
- StackDetector: Detect tech stack and extract routes/endpoints
- extract_features: Transform detection result into Autocoder features
- extract_from_project: One-step detection and feature extraction
"""

from .base_analyzer import BaseAnalyzer
from .feature_extractor import (
    DetectedFeature,
    FeatureExtractionResult,
    extract_features,
    extract_from_project,
    features_to_bulk_create_format,
)
from .stack_detector import StackDetectionResult, StackDetector

__all__ = [
    # Stack Detection
    "StackDetector",
    "StackDetectionResult",
    "BaseAnalyzer",
    # Feature Extraction
    "DetectedFeature",
    "FeatureExtractionResult",
    "extract_features",
    "extract_from_project",
    "features_to_bulk_create_format",
]

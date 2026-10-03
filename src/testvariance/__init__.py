"""Offline analysis of comparable CI observations, without root-cause claims."""
from .core import InputError, Observation, analyze, load_jsonl, wilson_interval

__all__ = ["InputError", "Observation", "analyze", "load_jsonl", "wilson_interval"]
__version__ = "0.1.0"

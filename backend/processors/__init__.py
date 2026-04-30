"""Processors package: contains processing logic wrappers.

For now this package provides a thin proxy to the existing top-level
`procesador.py` so we can later move the implementation here safely.
"""

from .procesador import procesar_excel

__all__ = ["procesar_excel"]

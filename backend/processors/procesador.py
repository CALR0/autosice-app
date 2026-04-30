"""Processor proxy module.

Now this proxies to `processors.impl` where the full implementation was
migrated. This keeps the public API `processors.procesador.procesar_excel`
stable while the implementation lives in `processors.impl`.
"""
from processors.impl import procesar_excel  # re-export the implementation

__all__ = ["procesar_excel"]

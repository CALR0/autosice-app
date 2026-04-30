"""Text normalization and parsing helpers.

These are extracted from the original `procesador.py` to centralize
common text-processing utilities.
"""
import unicodedata
import re


def normalizar(texto):
    texto = str(texto).lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def resolver_captcha(texto):
    numeros = list(map(int, re.findall(r'\d+', texto)))
    return sum(numeros)


def parse_number(value):
    try:
        if value is None:
            return None
        s = str(value).strip()
        if s == "":
            return None
        s_clean = re.sub(r"[^0-9.,-]", "", s)
        try:
            return float(s_clean.replace(',', ''))
        except Exception:
            try:
                return float(s_clean.replace('.', '').replace(',', '.'))
            except Exception:
                return None
    except Exception:
        return None

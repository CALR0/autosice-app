"""Excel helpers: reading/writing and simple row counting utilities."""
import pandas as pd


def count_data_rows(path: str) -> int:
    """Return number of data rows in the Excel file (including all rows read by pandas).

    This is intentionally simple; later we can add heuristics to detect headers
    or skip empty rows. For now it returns the dataframe row count.
    """
    df = pd.read_excel(path)
    return int(df.shape[0])


def read_excel(path: str):
    return pd.read_excel(path)

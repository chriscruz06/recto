"""recto: scan preprocessing for early-modern printed books.

A scanned page image of a hand-press book is usually a two-page spread, and
the text on each page is set in columns. Recto cuts that image down to one
clean image per text column, and records where every column came from.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]

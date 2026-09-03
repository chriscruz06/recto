# recto

Cleans scanned early-modern book spreads into OCR-ready column images.

A scanned page of a hand-press book is usually a photograph of a two-page
spread, and the text on each page is set in columns. Point an OCR engine at
that image and it reads straight across every column at once, producing text
that is worse than useless because it looks plausible. Recto cuts the image
down to one clean image per text column, and writes a manifest saying where
each column came from.

Developed against Albertus Magnus, *Super Iohannem*, in the Jammy edition
(Lugduni, 1651, *Operum Tomus Undecimus*).

## Status

Early. The command-line skeleton is in place and the processing stages are
being added one at a time. See `docs/` once it exists, and the build plan for
the order things land in.

## Install

```
git clone <your remote here>
cd recto
pip install -e ".[dev]"
recto --help
```

Python 3.11 or newer.

## License

MIT. See `LICENSE`.

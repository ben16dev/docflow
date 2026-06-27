from typing import List, Tuple


PageRange = Tuple[int, int]


def parse_ranges(ranges_text: str) -> List[PageRange]:
    """
    Convierte texto tipo:
    1-3, 5, 8-10

    En:
    [(1, 3), (5, 5), (8, 10)]
    """

    if not ranges_text or not ranges_text.strip():
        raise ValueError("Introduce un rango de páginas.")

    parts = [p.strip() for p in ranges_text.split(",") if p.strip()]

    if not parts:
        raise ValueError("Introduce un rango de páginas válido.")

    ranges = []

    for part in parts:
        if "-" in part:
            a, b = part.split("-", 1)

            if not a.strip().isdigit() or not b.strip().isdigit():
                raise ValueError(f"Rango inválido: '{part}'")

            start = int(a)
            end = int(b)

            if start <= 0 or end <= 0 or start > end:
                raise ValueError(f"Rango inválido: '{part}'")

            ranges.append((start, end))

        else:
            if not part.isdigit() or int(part) <= 0:
                raise ValueError(f"Página inválida: '{part}'")

            page = int(part)
            ranges.append((page, page))

    return ranges


def expand_ranges_to_pages(ranges: List[PageRange], max_pages: int) -> List[int]:
    """
    Expande rangos a lista de páginas.
    """

    pages = []

    for start, end in ranges:
        if start > max_pages or end > max_pages:
            raise ValueError(
                f"El PDF tiene {max_pages} páginas. "
                f"Rango fuera de límites: {start}-{end}"
            )

        pages.extend(range(start, end + 1))

    return pages


def ranges_to_pages_set(ranges: List[PageRange], max_pages: int) -> set[int]:
    """
    Expande rangos a set de páginas.
    """

    return set(expand_ranges_to_pages(ranges, max_pages))
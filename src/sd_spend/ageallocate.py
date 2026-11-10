"""Allocate each federal program's dollars across age brackets, and say how each split was made."""

BANDS = (("0-18", 0, 18), ("19-44", 19, 44), ("45-64", 45, 64), ("65-84", 65, 84), ("85+", 85, 200))
KEYS = [b[0] for b in BANDS]
# Pew birth years; Gen Alpha is 2013 on.
GENERATIONS = (("Silent", 0, 1945), ("Baby Boomers", 1946, 1964), ("Gen X", 1965, 1980), ("Millennials", 1981, 1996),
               ("Gen Z", 1997, 2012), ("Gen Alpha", 2013, 9999))


class AllocationError(ValueError):
    pass


def band_of(age: int) -> str:
    return next(key for key, lo, hi in BANDS if lo <= age <= hi)


def population_by_band(pop: dict[int, int]) -> dict[str, int]:
    out = dict.fromkeys(KEYS, 0)
    for age, n in pop.items():
        out[band_of(age)] += n
    return out


def spread_ages(total: float, lo: int, hi: int, pop: dict[int, int]) -> dict[str, float]:
    """Spread a dollar total over ages lo..hi in proportion to population, summed into brackets."""
    ages = [a for a in range(lo, hi + 1) if a in pop]
    weight = sum(pop[a] for a in ages)
    if weight <= 0:
        raise AllocationError(f"no population at ages {lo}-{hi}")
    out = dict.fromkeys(KEYS, 0.0)
    for a in ages:
        out[band_of(a)] += total * pop[a] / weight
    return out


def add(*parts: dict[str, float]) -> dict[str, float]:
    return {k: sum(p.get(k, 0.0) for p in parts) for k in KEYS}


def scale(by_band: dict[str, float], total: float) -> dict[str, float]:
    have = sum(by_band.values())
    if have <= 0:
        raise AllocationError("nothing to scale")
    return {k: v * total / have for k, v in by_band.items()}


def from_shares(total: float, shares: dict[str, float]) -> dict[str, float]:
    return {k: total * shares[k] for k in KEYS}


def ssa_workers_and_children(pairs: list[tuple[int, float]]) -> dict[str, float]:
    out = dict.fromkeys(KEYS, 0.0)
    for age, dollars in pairs:
        out[band_of(age)] += dollars
    return out


def ssa_other_adults(coarse: dict[str, float], pop: dict[int, int]) -> dict[str, float]:
    """Spouse and survivor benefits only come in three age groups; spread each over its ages by population."""
    return add(spread_ages(coarse["under 62"], 19, 61, pop), spread_ages(coarse["62-64"], 62, 64, pop),
               spread_ages(coarse["65 or older"], 65, 110 if max(pop) >= 110 else max(pop), pop))


def va_bands(bands: dict[str, int], dollars: float, pop: dict[int, int], ranges: dict[str, tuple[int, int]]) -> dict[str, float]:
    """VA recipients by its own age bands; dollars follow the recipient counts, then spread within each band by population."""
    n = sum(bands.values())
    return add(*[spread_ages(dollars * count / n, *ranges[name], pop) for name, count in bands.items()])


def generation_labels(band: tuple[str, int, int], pop: dict[int, int], year: int, minimum: float = 0.10) -> list[str]:
    key, lo, hi = band
    ages = [a for a in pop if lo <= a <= hi]
    total = sum(pop[a] for a in ages)
    out = []
    for name, first, last in GENERATIONS:
        n = sum(pop[a] for a in ages if first <= year - a <= last)
        if total and n / total >= minimum:
            out.append(name)
    return out


def by_parent_age(total: float, child_lo: int, child_hi: int, pop: dict[int, int], births: list[tuple[int, int, int]]) -> dict[str, float]:
    """Put a credit at the likely age of the parent: a child's age plus the mother's age at birth.

    Children are weighted by population; mothers' ages at birth by the year's births, spread evenly within each age group.
    Fathers and other claimants are not modelled (they are typically a few years older)."""
    kids = sum(pop[a] for a in range(child_lo, child_hi + 1))
    mothers = sum(n for _, _, n in births)
    if kids <= 0 or mothers <= 0:
        raise AllocationError("no children or births to place a credit by parent age")
    out = dict.fromkeys(KEYS, 0.0)
    for age in range(child_lo, child_hi + 1):
        for lo, hi, n in births:
            share = total * (pop[age] / kids) * (n / mothers) / (hi - lo + 1)
            for mother in range(lo, hi + 1):
                out[band_of(min(age + mother, 100))] += share
    return out

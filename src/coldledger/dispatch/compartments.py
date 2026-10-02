from dataclasses import dataclass

def _tags(value):
    if value is None:
        return frozenset()
    if isinstance(value, (set, frozenset, tuple, list)):
        return frozenset(value)
    return frozenset((value,))

@dataclass(frozen=True)
class Shipment:
    shipment_id: str
    low: float
    high: float
    volume: float
    incompatible: frozenset
    tags: frozenset
    # Qualifications the carrying compartment must provide (positive match).
    requires: frozenset = frozenset()
    # Labels/qualifications this shipment refuses on the compartment side.
    restrictions: frozenset = frozenset()
    # Packaging classes this shipment presents/accepts (symmetric match).
    packaging: frozenset = frozenset()

@dataclass(frozen=True)
class Compartment:
    compartment_id: str
    setpoint: float
    capacity: float
    # Qualifications the compartment is certified to provide.
    provides: frozenset = frozenset()
    # Labels/cargo the compartment forbids (e.g. dangerous-goods bans).
    restrictions: frozenset = frozenset()
    # Packaging classes the compartment is fitted to carry.
    packaging: frozenset = frozenset()

def cargo_conflict(a, b):
    """Symmetric dangerous-label check between two shipments.

    Loading is forbidden when *either* side declares a restriction that
    matches the other side's labels; a one-sided declaration is not enough.
    """
    return bool((a.incompatible & b.tags) or (b.incompatible & a.tags))

def compartment_qualified(shipment, compartment):
    """Symmetric qualification/label check between cargo and a compartment.

    Both directions must hold: the compartment must provide everything the
    shipment requires, and a restriction declared by either party against a
    label the other party carries forbids the pairing.
    """
    if not _tags(shipment.requires) <= _tags(compartment.provides):
        return False
    if _tags(shipment.restrictions) & _tags(compartment.provides):
        return False
    if _tags(compartment.restrictions) & _tags(shipment.tags):
        return False
    if _tags(shipment.packaging) and _tags(compartment.packaging):
        if not (_tags(shipment.packaging) & _tags(compartment.packaging)):
            return False
    return True

def _fits(shipment, compartment, remaining, contents):
    if not shipment.low <= compartment.setpoint <= shipment.high:
        return False
    if remaining[compartment.compartment_id] < shipment.volume:
        return False
    if not compartment_qualified(shipment, compartment):
        return False
    for other in contents[compartment.compartment_id]:
        if cargo_conflict(shipment, other):
            return False
    return True

def assign(shipments, compartments):
    """Assign every shipment atomically; either all load or none do.

    Compatibility is judged symmetrically for cargo dangerous labels,
    compartment qualifications and packaging requirements. When a greedy
    placement blocks a later shipment, earlier shipments are moved to other
    compartments (re-cabin) before the whole consignment is rejected, so
    capacity is never occupied for a plan that later proves incompatible.
    """
    order = sorted(shipments, key=lambda s: (-s.volume, s.shipment_id))
    remaining = {c.compartment_id: c.capacity for c in compartments}
    contents = {c.compartment_id: [] for c in compartments}
    assignment = {}

    def options(shipment):
        rows = [c for c in compartments if _fits(shipment, c, remaining, contents)]
        rows.sort(key=lambda c: (remaining[c.compartment_id] - shipment.volume,
                                 c.compartment_id))
        return rows

    def place(index):
        if index == len(order):
            return True
        shipment = order[index]
        for compartment in options(shipment):
            cid = compartment.compartment_id
            remaining[cid] -= shipment.volume
            contents[cid].append(shipment)
            assignment[shipment.shipment_id] = cid
            if place(index + 1):
                return True
            contents[cid].pop()
            remaining[cid] += shipment.volume
            del assignment[shipment.shipment_id]
        return False

    if not place(0):
        raise ValueError('no compatible compartment')
    return assignment

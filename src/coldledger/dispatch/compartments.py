from dataclasses import dataclass, field


@dataclass(frozen=True)
class Shipment:
    shipment_id: str
    low: float
    high: float
    volume: float
    # 危险标签：本票声明的标签，以及声明不与之为伍的标签（保持原位置顺序）
    incompatible: frozenset = field(default_factory=frozenset)
    tags: frozenset = field(default_factory=frozenset)
    # 舱位资格：本票需要/具备的资格，以及不接受的舱位资格
    qualifications: frozenset = field(default_factory=frozenset)
    forbidden_qualifications: frozenset = field(default_factory=frozenset)
    # 包装要求：本票采用/需要的包装类别，以及不接受的包装类别
    packaging: frozenset = field(default_factory=frozenset)
    forbidden_packaging: frozenset = field(default_factory=frozenset)


@dataclass(frozen=True)
class Compartment:
    compartment_id: str
    setpoint: float
    capacity: float
    # 舱位资格：本舱具备的资格，以及拒收的资格（如未取得该危险品资质）
    qualifications: frozenset = field(default_factory=frozenset)
    forbidden_qualifications: frozenset = field(default_factory=frozenset)
    # 包装要求：本舱声明支持的包装类别，以及拒收的包装类别
    packaging: frozenset = field(default_factory=frozenset)
    forbidden_packaging: frozenset = field(default_factory=frozenset)


def _symmetric_clash(declared_a, forbidden_a, declared_b, forbidden_b):
    """对称判断：任一方声明的标签/资格/包装都不得落在另一方声明的限制内。

    只查 declared_a & forbidden_b 会漏掉"对方声明、我方限制"这一方向，
    因此两个方向都必须检查。
    """
    return bool(declared_a & forbidden_b or declared_b & forbidden_a)


def cargo_compatible(a, b):
    """两票货物能否同舱：危险标签双向互不冲突。"""
    return not _symmetric_clash(a.tags, a.incompatible, b.tags, b.incompatible)


def shipment_fits(shipment, compartment):
    """货物与舱位是否兼容：舱位资格、包装要求均做对称（双向）判断。"""
    if _symmetric_clash(
        shipment.qualifications, shipment.forbidden_qualifications,
        compartment.qualifications, compartment.forbidden_qualifications,
    ):
        return False
    if _symmetric_clash(
        shipment.packaging, shipment.forbidden_packaging,
        compartment.packaging, compartment.forbidden_packaging,
    ):
        return False
    return True


def assign(shipments, compartments):
    remaining = {c.compartment_id: c.capacity for c in compartments}
    contents = {c.compartment_id: [] for c in compartments}
    out = {}
    for s in sorted(shipments, key=lambda x: (-x.volume, x.shipment_id)):
        candidates = []
        for c in compartments:
            # 先做完所有兼容性校验，任何一项不过就换下一个舱，绝不先扣容量
            if not s.low <= c.setpoint <= s.high:
                continue
            if remaining[c.compartment_id] < s.volume:
                continue
            if not shipment_fits(s, c):
                continue
            if any(not cargo_compatible(s, e) for e in contents[c.compartment_id]):
                continue
            candidates.append(c)
        if not candidates:
            # 所有舱都不兼容（含对称标签/资格/包装冲突）：整票拒绝，不留半成品
            raise ValueError(f'no compatible compartment for shipment {s.shipment_id}')
        # 校验全部通过后才占用容量
        c = min(candidates, key=lambda x: (remaining[x.compartment_id] - s.volume, x.compartment_id))
        remaining[c.compartment_id] -= s.volume
        contents[c.compartment_id].append(s)
        out[s.shipment_id] = c.compartment_id
    return out

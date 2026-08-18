"""사냥터와 몬스터 출현."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from functools import lru_cache

from tamer import network
from tamer.data import DATA_DIR, GRADE_ORDER, GameData, Species
from tamer.models import Monster

UNKNOWN_ISLAND = "미지의 섬"


@dataclass
class Area:
    name: str
    element: str
    min_level: int
    max_level: int
    min_grade: int
    max_grade: int
    pool: list[Species] = field(default_factory=list)

    def describe(self) -> str:
        band = GRADE_ORDER[self.min_grade]
        if self.max_grade != self.min_grade:
            band += f"~{GRADE_ORDER[self.max_grade]}"
        element = "전속성" if self.element == "전속성" else f"{self.element}속성"
        return f"{self.name:<12s} {element}  Lv{self.min_level}~{self.max_level}  {band}"


@lru_cache(maxsize=1)
def _area_config() -> list[dict]:
    payload = json.loads((DATA_DIR / "world.json").read_text(encoding="utf-8"))
    return payload["areas"]


def build_areas(data: GameData) -> list[Area]:
    areas = []
    for entry in _area_config():
        low = GRADE_ORDER.index(entry["grades"][0])
        high = GRADE_ORDER.index(entry["grades"][1])
        pool = [
            species
            for species in data.filter(element=entry["element"])
            if low <= species.grade_index <= high
        ]
        # 주속성만으로 후보가 부족하면 같은 등급대의 다른 속성으로 채운다.
        if len(pool) < 3:
            pool += [
                species
                for species in data.species
                if low <= species.grade_index <= high and species not in pool
            ]
        areas.append(
            Area(entry["name"], entry["element"], entry["levels"][0], entry["levels"][1], low, high, pool)
        )
    areas.append(Area(UNKNOWN_ISLAND, "전속성", 1, 99, 0, len(GRADE_ORDER) - 1, list(data.species)))
    return areas


def spawn(
    area: Area,
    data: GameData,
    rng: random.Random,
    hero_level: int = 1,
    island_level: int = 1,
) -> list[Monster]:
    """사냥터에서 적 파티(1~2마리)를 만든다.

    미지의 섬은 주인공과 비슷한 레벨의 몬스터가 등급에 상관없이 나오고,
    섬 레벨이 오를수록 상위 등급이 열린다.
    """
    if area.name == UNKNOWN_ISLAND:
        cap = network.island_grade_cap(data, island_level)
        pool = [species for species in area.pool if species.grade_index <= cap]
        level_range = (max(1, hero_level - 2), hero_level + 2)
        # 섬 레벨이 오르면 하위 등급이 밀려나고 상위 등급이 흔해진다.
        floor = max(0, cap - 2)
        pool = [species for species in pool if species.grade_index >= floor] or pool
    else:
        pool = area.pool
        level_range = (area.min_level, area.max_level)
        floor = area.min_grade

    # 상위 등급일수록 드물게 나온다.
    weights = [max(1, 64 >> (max(0, species.grade_index - floor) * 2)) for species in pool]
    count = 1 if rng.random() < 0.7 else 2
    enemies = []
    for _ in range(count):
        species = rng.choices(pool, weights=weights, k=1)[0]
        enemies.append(Monster(species, data, level=rng.randint(*level_range)))
    return enemies

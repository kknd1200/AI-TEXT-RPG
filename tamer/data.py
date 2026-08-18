"""도감 · 패시브 스킬 · 아이템 · 밸런스 계수를 읽어 들인다.

기본값은 이 저장소의 오리지널 도감(data/roster.json)이다.
data/extracted/monsters.json 이 있으면 그쪽을 대신 쓸 수 있는데, 그건 각자
tools/extract_apk.py 로 직접 뽑아 넣은 파일이고 저장소에는 포함하지 않는다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RULES_DIR = DATA_DIR / "rules"
ROSTER_PATH = DATA_DIR / "roster.json"
EXTRACTED_ROSTER = DATA_DIR / "extracted" / "monsters.json"
EXTRACTED_GROWTH = DATA_DIR / "extracted" / "element_growth.json"

GRADE_ORDER = ["common", "uncommon", "rare", "special", "legend", "god"]
STAT_KEYS = ["str", "dex", "mstr", "int", "con", "spd"]


@dataclass(frozen=True)
class Species:
    """도감에 실린 몬스터 한 종."""

    index: int
    name: str
    element: str
    grade: str
    skill_name: str
    skill_description: str
    base_stats: dict[str, int]
    growth: dict[str, int]

    @property
    def grade_index(self) -> int:
        return GRADE_ORDER.index(self.grade)

    def __str__(self) -> str:
        return f"{self.name}({self.element}/{self.grade})"


@dataclass(frozen=True)
class Passive:
    """패시브 스킬 한 종. kind 가 전투 엔진이 알아보는 효과 종류다."""

    id: str
    name: str
    description: str
    kind: str
    levels: list[float]
    materials: dict[str, int]

    def magnitude(self, level: int) -> float:
        return self.levels[min(max(level, 1), len(self.levels)) - 1]

    @property
    def max_level(self) -> int:
        return len(self.levels)


@dataclass(frozen=True)
class GameData:
    species: list[Species]
    passives: list[Passive]
    items: dict[str, dict]
    drops: dict[str, list[str]]
    slots: dict[str, int]
    balance: dict
    source: str

    # ---------------------------------------------------------------- 조회

    def by_name(self, name: str) -> Species:
        for entry in self.species:
            if entry.name == name:
                return entry
        raise KeyError(name)

    def filter(self, element: str | None = None, grade: str | None = None) -> list[Species]:
        return [
            entry
            for entry in self.species
            if (element is None or entry.element == element)
            and (grade is None or entry.grade == grade)
        ]

    def passive(self, passive_id: str) -> Passive:
        for entry in self.passives:
            if entry.id == passive_id:
                return entry
        raise KeyError(passive_id)

    def item(self, name: str) -> dict:
        return self.items[name]

    @property
    def elements(self) -> list[str]:
        seen: list[str] = []
        for entry in self.species:
            if entry.element not in seen:
                seen.append(entry.element)
        return seen


def _read(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"{path} 가 없다. `python3 tools/generate_roster.py` 로 도감을 만든다.")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_species() -> tuple[list[Species], str]:
    """도감을 읽는다. TAMER_ROSTER=extracted 면 직접 추출한 데이터를 쓴다."""
    use_extracted = os.environ.get("TAMER_ROSTER") == "extracted"
    if use_extracted and EXTRACTED_ROSTER.exists():
        payload = _read(EXTRACTED_ROSTER)
        growth_table = _read(EXTRACTED_GROWTH)["table"]
        species = [
            Species(
                index=entry["index"],
                name=entry["name"],
                element=entry["element"],
                grade=entry["grade"],
                skill_name=entry["active_skill"]["name"],
                skill_description=entry["active_skill"]["description"],
                base_stats=dict(entry["base_stats"]),
                # 추출 데이터는 성장치가 속성×등급 표로 따로 들어 있다.
                growth=dict(growth_table[entry["element"]][entry["grade"]]),
            )
            for entry in payload["monsters"]
        ]
        return species, str(EXTRACTED_ROSTER)

    payload = _read(ROSTER_PATH)
    species = [
        Species(
            index=entry["index"],
            name=entry["name"],
            element=entry["element"],
            grade=entry["grade"],
            skill_name=entry["active_skill"]["name"],
            skill_description=entry["active_skill"]["description"],
            base_stats=dict(entry["base_stats"]),
            growth=dict(entry["growth"]),
        )
        for entry in payload["monsters"]
    ]
    return species, str(ROSTER_PATH)


@lru_cache(maxsize=1)
def load_game_data() -> GameData:
    species, source = _load_species()
    passive_payload = _read(DATA_DIR / "passives.json")
    item_payload = _read(DATA_DIR / "items.json")
    return GameData(
        species=species,
        passives=[
            Passive(
                id=entry["id"],
                name=entry["name"],
                description=entry["description"],
                kind=entry["kind"],
                levels=list(entry["levels"]),
                materials=dict(entry["materials"]),
            )
            for entry in passive_payload["passives"]
        ],
        items=item_payload["items"],
        drops={k: v for k, v in item_payload["drops"].items() if not k.startswith("_")},
        slots=passive_payload["slots"],
        balance=_read(RULES_DIR / "balance.json"),
        source=source,
    )

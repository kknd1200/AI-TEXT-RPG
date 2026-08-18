"""주인공과 몬스터 개체."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from tamer.data import GRADE_ORDER, GameData, Species

STAT_NAMES = {
    "str": "STR(물리공격)",
    "dex": "DEX(물리방어)",
    "mstr": "MSTR(스킬공격)",
    "int": "INT(스킬방어)",
    "con": "CON(체력)",
    "spd": "SPD(속도)",
}


@dataclass
class Learned:
    """몬스터가 장착한 패시브 스킬 하나. 한 번 붙이면 뗄 수 없다."""

    passive_id: str
    level: int = 1


# eq=False: 스탯이 똑같은 두 마리가 값 비교로 같아지면 전투 엔진이 아군과 적을
# 구분하지 못한다(같은 종끼리 붙었을 때 적이 자기 편을 때린다). 개체는 항상
# 동일성으로 비교한다.
@dataclass(eq=False)
class Monster:
    """파티에 넣거나 상대로 만나는 몬스터 한 마리."""

    species: Species
    data: GameData
    level: int = 1
    brain: int = 0
    feel: int = 0
    food: int = 100
    evolved: bool = False
    experience: int = 0
    passives: list[Learned] = field(default_factory=list)
    hp: int = field(default=0)
    sp: int = field(default=0)
    # 전투 중에만 쓰는 상태
    guarding: bool = False
    rage_stacks: int = 0
    endured: bool = False

    def __post_init__(self) -> None:
        if self.hp <= 0:
            self.hp = self.max_hp
        if self.sp <= 0:
            self.sp = self.max_sp

    # ------------------------------------------------------------------ 스탯

    def stat(self, key: str) -> int:
        """레벨 · 지능 · 허기도 · 진화를 반영한 최종 스탯.

        base + growth × (레벨-1) / divisor 형태이고, 계수는 balance.json 에 있다.
        패시브 보정은 전투 계산에서 따로 얹는다.
        """
        balance = self.data.balance
        base = self.species.base_stats[key]
        growth = self.species.growth[key]
        divisor = balance["growth"]["growth_divisor"]
        value = base + math.floor(growth * (self.level - 1) / divisor)
        value += self.brain // 10                       # BRAIN: 강화로 오르는 지능
        if self.evolved:
            value = math.floor(value * balance["condition"]["evolution_bonus"])
        if self.food <= 0:
            value = math.floor(value * balance["condition"]["starving_penalty"])
        return max(1, value)

    @property
    def stats(self) -> dict[str, int]:
        return {key: self.stat(key) for key in STAT_NAMES}

    @property
    def max_hp(self) -> int:
        vitals = self.data.balance["vitals"]
        return (
            vitals["hp_base"]
            + self.stat("con") * vitals["hp_per_con"]
            + self.level * vitals["hp_per_level"]
        )

    @property
    def max_sp(self) -> int:
        vitals = self.data.balance["vitals"]
        return (
            vitals["sp_base"]
            + self.stat("int") * vitals["sp_per_int"]
            + self.level * vitals["sp_per_level"]
        )

    @property
    def base_skill_cost(self) -> int:
        cost = self.data.balance["skill_cost"]
        # 진화하면 스킬이 강해지는 대신 SP 소모가 는다.
        base = cost["base"] + (self.level // 5) * cost["per_five_levels"]
        return base * 2 if self.evolved else base

    @property
    def party_cost(self) -> int:
        return self.data.balance["party_cost"][self.species.grade]

    @property
    def slot_limit(self) -> int:
        slots = self.data.slots
        return slots["evolved"] if self.evolved else slots["base"]

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def name(self) -> str:
        return self.species.name

    @property
    def element(self) -> str:
        return self.species.element

    # ------------------------------------------------------------- 패시브

    def has_passive(self, passive_id: str) -> bool:
        return any(entry.passive_id == passive_id for entry in self.passives)

    def passive_level(self, passive_id: str) -> int:
        for entry in self.passives:
            if entry.passive_id == passive_id:
                return entry.level
        return 0

    def passive_names(self) -> list[str]:
        return [
            f"{self.data.passive(entry.passive_id).name}Lv{entry.level}"
            for entry in self.passives
        ]

    # ------------------------------------------------------------- 성장/상태

    def experience_to_next(self) -> int:
        curve = self.data.balance["experience"]["level_curve"]
        return curve * self.level * self.level // 10 + 20

    def gain_experience(self, amount: int) -> list[str]:
        log: list[str] = []
        cap = self.data.balance["experience"]["max_level"]
        self.experience += amount
        while self.level < cap and self.experience >= self.experience_to_next():
            self.experience -= self.experience_to_next()
            self.level += 1
            self.hp = self.max_hp
            self.sp = self.max_sp
            log.append(f"{self.name}의 레벨이 {self.level}이 되었다!")
        return log

    def gain_feel(self, amount: int) -> list[str]:
        """교감도가 최대치에 닿으면 진화한다."""
        condition = self.data.balance["condition"]
        if self.evolved:
            self.feel = min(condition["feel_max"], self.feel + amount)
            return []
        self.feel += amount
        if self.feel < condition["feel_max"]:
            return []
        self.feel = 0
        self.evolved = True
        self.hp = self.max_hp
        return [
            f"{self.name}의 교감도가 최대치에 달했다. {self.name}(이)가 진화했다!"
            f" (패시브 슬롯 {self.slot_limit}칸)"
        ]

    def consume_food(self, ratio: float = 1.0) -> list[str]:
        condition = self.data.balance["condition"]
        before = self.food
        cost = max(1, round(condition["food_per_battle"] * ratio)) if ratio > 0 else 0
        self.food = max(0, self.food - cost)
        if before > 0 and self.food == 0:
            return [f"{self.name}의 허기도가 0이 되어 능력치가 떨어졌다."]
        return []

    def feed(self, element: str) -> list[str]:
        """마블을 먹인다. 같은 속성이면 교감도가 크게 오른다."""
        condition = self.data.balance["condition"]
        self.food = min(condition["food_max"], self.food + 40)
        gain = condition["feel_per_marble"] if element == self.element else 10
        return [f"{self.name}의 허기도를 채웠다."] + self.gain_feel(gain)

    def rest(self) -> None:
        self.hp = self.max_hp
        self.sp = self.max_sp
        self.guarding = False
        self.rage_stacks = 0
        self.endured = False

    def status_line(self) -> str:
        mark = "★" if self.evolved else " "
        line = (
            f"{mark}{self.name:<9s} {self.element} {self.species.grade:<9s} "
            f"Lv{self.level:<3d} HP {self.hp:>4d}/{self.max_hp:<4d} SP {self.sp:>3d}/{self.max_sp:<3d} "
            f"BRAIN {self.brain:>3d} FOOD {self.food:>3d} FEEL {self.feel:>3d} P{self.party_cost}"
        )
        if self.passives:
            line += "  [" + ", ".join(self.passive_names()) + "]"
        return line


@dataclass
class Hero:
    """주인공. 속성 · 등급 · 파티 포인트 · 소지품을 들고 있다."""

    name: str
    element: str
    data: GameData
    level: int = 1
    experience: int = 0
    stat_points: int = 0
    rank_index: int = 0
    gold: int = 500
    guild_rank: int = 99
    rank_points: int = 1000
    wins: int = 0
    losses: int = 0
    island_level: int = 1
    island_experience: int = 0
    party: list[Monster] = field(default_factory=list)
    storage: list[Monster] = field(default_factory=list)
    items: dict[str, int] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)

    @property
    def rank(self) -> str:
        return self.data.balance["rank_party_points"][self.rank_index]["rank"]

    @property
    def party_points(self) -> int:
        table = self.data.balance["rank_party_points"]
        bonus = self.data.balance["island"]["party_point_levels"]
        extra = sum(1 for threshold in bonus if self.island_level >= threshold)
        return table[self.rank_index]["points"] + extra

    @property
    def used_party_points(self) -> int:
        return sum(monster.party_cost for monster in self.party)

    def can_add(self, monster: Monster) -> bool:
        return self.used_party_points + monster.party_cost <= self.party_points

    def catch(self, monster: Monster) -> str:
        self.seen.add(monster.name)
        if self.can_add(monster):
            self.party.append(monster)
            return f"{monster.name}(이)가 파티에 합류했다."
        self.storage.append(monster)
        return f"{monster.name}(은)는 파티 포인트가 모자라 보관함으로 보냈다."

    def add_item(self, name: str, count: int = 1) -> None:
        self.items[name] = self.items.get(name, 0) + count

    def take_item(self, name: str, count: int = 1) -> bool:
        if self.items.get(name, 0) < count:
            return False
        self.items[name] -= count
        if self.items[name] == 0:
            del self.items[name]
        return True

    def experience_to_next(self) -> int:
        return 40 * self.level * self.level // 10 + 30

    def gain_experience(self, amount: int) -> list[str]:
        """주인공도 함께 성장한다. 레벨업마다 스탯 포인트 3개."""
        log: list[str] = []
        cap = self.data.balance["experience"]["max_level"]
        self.experience += amount
        while self.level < cap and self.experience >= self.experience_to_next():
            self.experience -= self.experience_to_next()
            self.level += 1
            self.stat_points += 3
            log.append(f"{self.name}의 레벨이 {self.level}이 되었다! (스탯 포인트 +3)")
        return log

    def promote(self) -> list[str]:
        """길드 랭킹이 오르면 등급과 파티 포인트가 함께 오른다."""
        table = self.data.balance["rank_party_points"]
        target = min(len(table) - 1, (99 - self.guild_rank) // 9)
        log = []
        while self.rank_index < target:
            self.rank_index += 1
            log.append(f"길드 등급이 {self.rank}(으)로 상승했다. (파티 포인트 {self.party_points})")
        return log

    @property
    def alive_party(self) -> list[Monster]:
        return [monster for monster in self.party if monster.alive]

    @property
    def all_monsters(self) -> list[Monster]:
        return self.party + self.storage

    def grade_of(self, grade: str) -> int:
        return GRADE_ORDER.index(grade)

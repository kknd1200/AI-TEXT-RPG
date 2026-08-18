"""패시브 스킬 효과 해석기.

패시브는 data/passives.json 에 kind 로 분류돼 있고, 전투 엔진은 이 모듈을 통해서만
그 값을 읽는다. 새 패시브를 추가할 때 kind 가 이미 있는 종류면 코드는 건드릴 필요가 없다.
"""

from __future__ import annotations

from tamer.models import Monster

RAGE_MAX_STACKS = 5
DESPERATE_HP_RATIO = 0.3


def magnitude(monster: Monster, kind: str) -> float:
    """같은 kind 의 패시브가 여러 개면 합산한다."""
    total = 0.0
    for learned in monster.passives:
        passive = monster.data.passive(learned.passive_id)
        if passive.kind == kind:
            total += passive.magnitude(learned.level)
    return total


def has(monster: Monster, kind: str) -> bool:
    return any(
        monster.data.passive(learned.passive_id).kind == kind
        for learned in monster.passives
    )


def attack_multiplier(monster: Monster, *, skill: bool, advantaged: bool) -> float:
    """공격 쪽 보정 배율."""
    bonus = magnitude(monster, "skill_up" if skill else "physical_up")
    if monster.hp <= monster.max_hp * DESPERATE_HP_RATIO:
        bonus += magnitude(monster, "desperate")
    bonus += magnitude(monster, "rage") * min(monster.rage_stacks, RAGE_MAX_STACKS)
    if advantaged:
        bonus += magnitude(monster, "affinity")
    return 1.0 + bonus


def defense_multiplier(monster: Monster, *, skill: bool) -> float:
    """받는 피해 배율. 1.0 미만이면 그만큼 덜 맞는다."""
    return max(0.2, 1.0 - magnitude(monster, "skill_guard" if skill else "physical_guard"))


def critical_bonus(monster: Monster) -> float:
    return magnitude(monster, "critical_up")


def speed_multiplier(monster: Monster) -> float:
    return 1.0 + magnitude(monster, "speed_up")


def pierce_ratio(monster: Monster) -> float:
    return min(0.6, magnitude(monster, "pierce"))


def guard_bonus(monster: Monster) -> float:
    return magnitude(monster, "guard_master")


def sp_cost(monster: Monster) -> int:
    saved = min(0.7, magnitude(monster, "sp_saver"))
    return max(1, round(monster.base_skill_cost * (1.0 - saved)))


def drain_ratio(monster: Monster) -> float:
    return magnitude(monster, "drain")


def regen_ratio(monster: Monster) -> float:
    return magnitude(monster, "regen")


def counter_chance(monster: Monster) -> float:
    return magnitude(monster, "counter")


def can_endure(monster: Monster) -> bool:
    return has(monster, "endure") and not monster.endured


def capture_bonus(monster: Monster) -> float:
    return magnitude(monster, "hunter")


def food_ratio(monster: Monster) -> float:
    """미식가는 허기 소모를 줄인다. 여러 개 붙어도 절반까지만."""
    return 0.5 if has(monster, "gourmet") else 1.0


def feel_ratio(monster: Monster) -> float:
    return 1.0 + magnitude(monster, "bond")


def turn_priority(monster: Monster) -> int:
    """선공 패시브가 있으면 같은 속도에서 먼저 움직인다."""
    return 1 if has(monster, "first_strike") else 0

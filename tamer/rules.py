"""전투 계산식. 계수는 전부 data/rules/balance.json 에서 온다."""

from __future__ import annotations

import math
import random

from tamer import passives
from tamer.models import Monster


def element_multiplier(balance: dict, attacker: str, defender: str) -> float:
    """속성 상성 배율. 물리 공격은 상성을 무시하고 스킬 공격에만 적용된다."""
    chart = balance["element_chart"]
    strong = chart["strong_against"]
    if defender in strong.get(attacker, []):
        return chart["advantage_multiplier"]
    if attacker in strong.get(defender, []):
        return chart["disadvantage_multiplier"]
    return 1.0


def physical_element_multiplier(balance: dict, attacker: str, defender: str) -> float:
    """물리 공격이 받는 상성 배율.

    상성을 완전히 무시하면 물리형 몬스터가 속성 체계 바깥에 서 버려서, 상성이
    유리한 상대가 오히려 지는 일이 생긴다. 그래서 물리에는 배율을 약하게만 준다.
    """
    weight = balance["element_chart"].get("physical_weight", 0.0)
    return 1.0 + (element_multiplier(balance, attacker, defender) - 1.0) * weight


def element_hint(balance: dict, attacker: str, defender: str) -> str:
    multiplier = element_multiplier(balance, attacker, defender)
    if multiplier > 1.0:
        return " 효과가 굉장했다!"
    if multiplier < 1.0:
        return " 효과가 별로였다..."
    return ""


def effective_speed(monster: Monster) -> float:
    return monster.stat("spd") * passives.speed_multiplier(monster)


def estimate_damage(balance: dict, attacker: Monster, defender: Monster, *, skill: bool) -> float:
    """난수를 뺀 기대 피해량. 자동 전투가 물리와 스킬 중 어느 쪽이 나은지 볼 때 쓴다."""
    setting = balance["damage"]
    if skill:
        attack = attacker.stat("mstr") * setting["skill_attack_scale"]
        defense = defender.stat("int") * setting["skill_defense_scale"]
        multiplier = element_multiplier(balance, attacker.element, defender.element)
    else:
        attack = attacker.stat("str") * setting["physical_attack_scale"]
        defense = defender.stat("dex") * setting["physical_defense_scale"]
        multiplier = physical_element_multiplier(balance, attacker.element, defender.element)
    attack *= passives.attack_multiplier(attacker, skill=skill, advantaged=multiplier > 1.0)
    defense *= 1.0 - passives.pierce_ratio(attacker)
    raw = (attack - defense) * multiplier
    raw *= passives.defense_multiplier(defender, skill=skill)
    return max(float(setting["minimum_damage"]), raw)


def damage(
    balance: dict,
    attacker: Monster,
    defender: Monster,
    *,
    skill: bool,
    rng: random.Random,
) -> tuple[int, bool, float]:
    """(피해량, 크리티컬 여부, 상성배율)을 돌려준다."""
    setting = balance["damage"]
    if skill:
        attack = attacker.stat("mstr") * setting["skill_attack_scale"]
        defense = defender.stat("int") * setting["skill_defense_scale"]
        multiplier = element_multiplier(balance, attacker.element, defender.element)
    else:
        attack = attacker.stat("str") * setting["physical_attack_scale"]
        defense = defender.stat("dex") * setting["physical_defense_scale"]
        multiplier = physical_element_multiplier(balance, attacker.element, defender.element)

    attack *= passives.attack_multiplier(attacker, skill=skill, advantaged=multiplier > 1.0)
    defense *= 1.0 - passives.pierce_ratio(attacker)

    raw = (attack - defense) * multiplier
    raw *= rng.uniform(setting["variance_min"], setting["variance_max"])

    critical = rng.random() < setting["critical_chance"] + passives.critical_bonus(attacker)
    if critical:
        raw *= setting["critical_multiplier"]
    if defender.guarding:
        reduction = setting["guard_reduction"] + passives.guard_bonus(defender)
        raw *= max(0.1, 1.0 - reduction)
    raw *= passives.defense_multiplier(defender, skill=skill)

    return max(setting["minimum_damage"], int(raw)), critical, multiplier


def flee_chance(balance: dict, runner: Monster, opponent: Monster) -> float:
    setting = balance["flee"]
    chance = setting["base_chance"] + (
        effective_speed(runner) - effective_speed(opponent)
    ) * setting["speed_weight"]
    return min(setting["max"], max(setting["min"], chance))


def capture_chance(
    balance: dict,
    target: Monster,
    hero_level: int,
    hero_element: str,
    ball: str = "몬스터볼",
    ball_bonus: float = 1.0,
    catcher: Monster | None = None,
) -> float:
    """주인공 레벨 이하만, HP가 낮을수록, 등급이 낮을수록 잘 잡힌다."""
    setting = balance["capture"]
    if target.level > hero_level:
        return 0.0
    chance = setting["grade_base"][target.species.grade]
    ratio = target.hp / max(1, target.max_hp)
    chance *= 1.0 - setting["hp_weight"] * ratio
    chance *= ball_bonus
    if target.element == hero_element:
        chance *= setting["same_element_bonus"]
    if catcher is not None:
        chance *= 1.0 + passives.capture_bonus(catcher)
    return min(0.95, max(0.0, chance))


def experience_reward(balance: dict, defeated: Monster, *, auto: bool = False) -> int:
    setting = balance["experience"]
    amount = (setting["base"] + setting["per_level"] * defeated.level) * setting[
        "grade_multiplier"
    ][defeated.species.grade]
    if auto:
        amount *= setting["auto_battle_ratio"]
    return max(1, math.floor(amount))


def gold_reward(balance: dict, defeated: Monster) -> int:
    setting = balance["experience"]
    return max(1, math.floor(defeated.level * 3 * setting["grade_multiplier"][defeated.species.grade]))

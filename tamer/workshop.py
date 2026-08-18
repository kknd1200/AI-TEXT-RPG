"""공방: 몬스터 조합 · 강화 · 패시브 스킬 장착.

  조합 — 같은 등급 두 마리를 합쳐 한 등급 위를 노린다. 실패하면 한 등급 아래가 나오고,
         최하위 등급은 실패해도 같은 등급이 나온다. 패시브는 확률로 계승된다.
  강화 — BRAIN(지능)을 올린다. 지능이 높을수록 성공률이 떨어진다.
  장착 — 재료와 골드를 들여 패시브를 붙인다. 한 번 붙이면 뗄 수 없고, 같은 스킬을
         두 번 붙일 수는 없지만 재료를 더 들여 레벨을 올릴 수는 있다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tamer.data import GRADE_ORDER, GameData
from tamer.models import Hero, Learned, Monster


@dataclass
class Outcome:
    ok: bool
    messages: list[str]
    monster: Monster | None = None


def _pick_species(data: GameData, rng: random.Random, element: str, grade: str):
    pool = data.filter(element=element, grade=grade) or data.filter(grade=grade)
    return rng.choice(pool)


def fusion_cost(data: GameData, grade: str) -> int:
    return data.balance["fusion"]["cost_gold"].get(grade, 0)


def fusion_rate(data: GameData, grade: str, catalyst: bool = False) -> float:
    setting = data.balance["fusion"]
    rate = setting["success_rate"].get(grade)
    if rate is None:
        return 0.0
    if catalyst:
        rate += data.items["조합촉매"]["fuse_bonus"]
    return min(0.95, rate)


def fuse(
    hero: Hero,
    first: Monster,
    second: Monster,
    rng: random.Random,
    *,
    catalyst: bool = False,
) -> Outcome:
    data = hero.data
    if first is second:
        return Outcome(False, ["같은 몬스터를 두 번 넣을 수는 없다."])
    if first.species.grade != second.species.grade:
        return Outcome(False, ["조합은 같은 등급끼리만 가능하다."])
    grade = first.species.grade
    if grade == GRADE_ORDER[-1]:
        return Outcome(False, ["god 등급은 더 위가 없다."])

    cost = fusion_cost(data, grade)
    if hero.gold < cost:
        return Outcome(False, [f"골드가 모자란다. ({cost} 필요)"])
    if catalyst and hero.items.get("조합촉매", 0) <= 0:
        return Outcome(False, ["조합촉매가 없다."])

    hero.gold -= cost
    if catalyst:
        hero.take_item("조합촉매")

    messages = [f"{first.name}(와)과 {second.name}(을)를 조합한다... (성공률 {fusion_rate(data, grade, catalyst):.0%})"]
    success = rng.random() < fusion_rate(data, grade, catalyst)
    index = GRADE_ORDER.index(grade)
    if success:
        next_grade = GRADE_ORDER[index + 1]
        messages.append("조합 성공!")
    else:
        next_grade = GRADE_ORDER[max(0, index - 1)]
        messages.append("조합 실패... 등급이 떨어진 몬스터가 나왔다.")

    element = rng.choice([first.element, second.element])
    species = _pick_species(data, rng, element, next_grade)
    result = Monster(
        species,
        data,
        level=max(1, (first.level + second.level) // 2),
        brain=(first.brain + second.brain) // 2,
    )

    # 패시브 계승: 두 재료의 패시브를 확률로 물려받는다.
    chance = data.balance["fusion"]["inherit_passive_chance"]
    inherited: list[Learned] = []
    for learned in first.passives + second.passives:
        if any(entry.passive_id == learned.passive_id for entry in inherited):
            continue
        if rng.random() < chance:
            inherited.append(Learned(learned.passive_id, learned.level))
    result.passives = inherited[: result.slot_limit]
    if result.passives:
        messages.append("계승한 패시브: " + ", ".join(result.passive_names()))

    for material in (first, second):
        if material in hero.party:
            hero.party.remove(material)
        elif material in hero.storage:
            hero.storage.remove(material)
    messages.append(hero.catch(result))
    return Outcome(True, messages, result)


def enhance_rate(data: GameData, monster: Monster, catalyst: bool = False) -> float:
    setting = data.balance["enhance"]
    rate = setting["base_rate"] - setting["decay_per_point"] * monster.brain
    if catalyst:
        rate += data.items["강화촉매"]["enhance_bonus"]
    return min(0.95, max(setting["min_rate"], rate))


def enhance_cost(data: GameData, monster: Monster) -> int:
    return data.balance["enhance"]["cost_gold_per_point"] * (monster.brain + 1)


def enhance(
    hero: Hero, monster: Monster, rng: random.Random, *, catalyst: bool = False
) -> Outcome:
    data = hero.data
    setting = data.balance["enhance"]
    if monster.brain >= setting["max_brain"]:
        return Outcome(False, [f"{monster.name}의 지능은 이미 최대다."])
    cost = enhance_cost(data, monster)
    if hero.gold < cost:
        return Outcome(False, [f"골드가 모자란다. ({cost} 필요)"])
    if catalyst and hero.items.get("강화촉매", 0) <= 0:
        return Outcome(False, ["강화촉매가 없다."])

    hero.gold -= cost
    if catalyst:
        hero.take_item("강화촉매")

    rate = enhance_rate(data, monster, catalyst)
    if rng.random() < rate:
        monster.brain += 1
        return Outcome(
            True,
            [f"강화 성공! {monster.name}의 BRAIN이 {monster.brain}이 되었다. (성공률 {rate:.0%})"],
            monster,
        )
    return Outcome(False, [f"강화 실패... (성공률 {rate:.0%})"], monster)


def attach_cost(data: GameData, monster: Monster, passive_id: str) -> tuple[int, dict[str, int]]:
    """(골드, 재료) — 이미 배운 스킬이면 레벨업 비용이 든다."""
    passive = data.passive(passive_id)
    setting = data.balance["skill_craft"]
    gold = setting["attach_gold"]
    materials = dict(passive.materials)
    level = monster.passive_level(passive_id)
    if level:
        gold = int(gold * setting["level_up_gold_multiplier"] * level)
        materials = {name: count * (level + 1) for name, count in materials.items()}
    return gold, materials


def attach_passive(hero: Hero, monster: Monster, passive_id: str) -> Outcome:
    data = hero.data
    passive = data.passive(passive_id)
    level = monster.passive_level(passive_id)

    if level == 0 and len(monster.passives) >= monster.slot_limit:
        return Outcome(False, [f"패시브 슬롯이 가득 찼다. ({monster.slot_limit}칸, 진화하면 늘어난다)"])
    if level >= passive.max_level:
        return Outcome(False, [f"{passive.name}(은)는 이미 최대 레벨이다."])

    gold, materials = attach_cost(data, monster, passive_id)
    if hero.gold < gold:
        return Outcome(False, [f"골드가 모자란다. ({gold} 필요)"])
    missing = [
        f"{name} {count - hero.items.get(name, 0)}개"
        for name, count in materials.items()
        if hero.items.get(name, 0) < count
    ]
    if missing:
        return Outcome(False, ["재료가 모자란다: " + ", ".join(missing)])

    hero.gold -= gold
    for name, count in materials.items():
        hero.take_item(name, count)

    if level:
        for learned in monster.passives:
            if learned.passive_id == passive_id:
                learned.level += 1
                return Outcome(
                    True, [f"{monster.name}의 {passive.name}(이)가 Lv{learned.level}이 되었다."], monster
                )
    monster.passives.append(Learned(passive_id, 1))
    return Outcome(True, [f"{monster.name}(이)가 {passive.name}(을)를 익혔다."], monster)

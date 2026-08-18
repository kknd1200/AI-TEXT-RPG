"""턴제 전투 엔진.

  - SPD가 높은 몬스터가 먼저 움직인다(선제 패시브는 동속도에서 우선권).
  - 커맨드는 물리공격 / 스킬공격 / 방어 / 아이템 / 도망 / 포획.
  - 물리 공격은 상성을 무시하고, 스킬 공격에만 속성 상성이 적용된다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tamer import passives, rules
from tamer.data import GameData
from tamer.models import Hero, Monster

ATTACK = "attack"
SKILL = "skill"
GUARD = "guard"
ITEM = "item"
FLEE = "flee"
CAPTURE = "capture"


@dataclass
class Action:
    kind: str
    actor: Monster
    target: Monster | None = None
    item: str | None = None


@dataclass
class Battle:
    data: GameData
    hero: Hero
    allies: list[Monster]
    enemies: list[Monster]
    rng: random.Random = field(default_factory=random.Random)
    capturable: bool = True
    log: list[str] = field(default_factory=list)
    result: str | None = None            # win / lose / fled / captured
    captured: Monster | None = None
    turn: int = 0
    gold: int = 0
    drops: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------------ 조회

    @property
    def balance(self) -> dict:
        return self.data.balance

    @property
    def finished(self) -> bool:
        return self.result is not None

    def living(self, side: list[Monster]) -> list[Monster]:
        return [monster for monster in side if monster.alive]

    def opponents_of(self, monster: Monster) -> list[Monster]:
        return self.enemies if any(monster is ally for ally in self.allies) else self.allies

    # -------------------------------------------------------------- 라운드

    def auto_action(self, actor: Monster) -> Action:
        """자동 전투 / 적 AI.

        상성만 보고 스킬을 고르면, 물리형 몬스터가 자기 약점인 스킬 공격을 상성
        보너스 때문에 쓰는 일이 생긴다. 그래서 두 커맨드의 기대 피해를 직접 비교한다.
        """
        targets = self.living(self.opponents_of(actor))
        if not targets:
            return Action(GUARD, actor)
        target = min(targets, key=lambda monster: monster.hp)
        physical = rules.estimate_damage(self.balance, actor, target, skill=False)
        if actor.sp < passives.sp_cost(actor):
            return Action(ATTACK, actor, target)
        skill = rules.estimate_damage(self.balance, actor, target, skill=True)
        return Action(SKILL if skill > physical else ATTACK, actor, target)

    def run_round(self, ally_actions: list[Action]) -> list[str]:
        """아군 커맨드를 받아 한 라운드를 진행하고 그 동안의 로그를 돌려준다."""
        if self.finished:
            return []
        self.turn += 1
        start = len(self.log)

        queue = list(ally_actions)
        queue += [self.auto_action(enemy) for enemy in self.living(self.enemies)]
        queue.sort(
            key=lambda action: (
                -rules.effective_speed(action.actor),
                -passives.turn_priority(action.actor),
                self.rng.random(),
            )
        )

        for monster in self.allies + self.enemies:
            monster.guarding = False
        for action in queue:
            if action.kind == GUARD:
                action.actor.guarding = True

        for action in queue:
            if self.finished:
                break
            if not action.actor.alive:
                continue
            self._resolve(action)
            self._check_end()

        self._tick_regeneration()
        self._check_end()
        return self.log[start:]

    def _tick_regeneration(self) -> None:
        for monster in self.living(self.allies) + self.living(self.enemies):
            ratio = passives.regen_ratio(monster)
            if ratio <= 0 or monster.hp >= monster.max_hp:
                continue
            healed = min(monster.max_hp - monster.hp, max(1, int(monster.max_hp * ratio)))
            monster.hp += healed
            self.log.append(f"{monster.name}의 재생! HP를 {healed} 회복했다.")

    # ------------------------------------------------------------- 커맨드

    def _resolve(self, action: Action) -> None:
        handler = {
            ATTACK: self._do_attack,
            SKILL: self._do_skill,
            GUARD: self._do_guard,
            ITEM: self._do_item,
            FLEE: self._do_flee,
            CAPTURE: self._do_capture,
        }[action.kind]
        handler(action)

    def _pick_target(self, action: Action) -> Monster | None:
        if action.target is not None and action.target.alive:
            return action.target
        alive = self.living(self.opponents_of(action.actor))
        return alive[0] if alive else None

    def _apply_damage(
        self, attacker: Monster, target: Monster, amount: int, *, physical: bool
    ) -> None:
        """피해 적용과 그에 딸린 패시브(근성 · 흡혈 · 분노 · 반격) 처리."""
        if amount >= target.hp and passives.can_endure(target):
            amount = target.hp - 1
            target.endured = True
            self.log.append(f"{target.name}의 근성! HP 1로 버텨냈다.")
        target.hp = max(0, target.hp - amount)
        target.rage_stacks += 1

        drain = passives.drain_ratio(attacker)
        if drain > 0 and attacker.alive:
            healed = min(attacker.max_hp - attacker.hp, max(1, int(amount * drain)))
            if healed > 0:
                attacker.hp += healed
                self.log.append(f"{attacker.name}의 흡혈! HP를 {healed} 회복했다.")

        if not target.alive:
            self.log.append(f"{target.name}(은)는 쓰러졌다.")
            return
        if physical and self.rng.random() < passives.counter_chance(target):
            back, _, _ = rules.damage(self.balance, target, attacker, skill=False, rng=self.rng)
            attacker.hp = max(0, attacker.hp - back)
            self.log.append(f"{target.name}의 반격! {attacker.name}에게 {back}의 피해")
            if not attacker.alive:
                self.log.append(f"{attacker.name}(은)는 쓰러졌다.")

    def _do_attack(self, action: Action) -> None:
        target = self._pick_target(action)
        if target is None:
            return
        amount, critical, _ = rules.damage(
            self.balance, action.actor, target, skill=False, rng=self.rng
        )
        text = f"{action.actor.name}의 물리 공격! {target.name}에게 {amount}의 피해"
        if critical:
            text += " (크리티컬!)"
        self.log.append(text)
        self._apply_damage(action.actor, target, amount, physical=True)

    def _do_skill(self, action: Action) -> None:
        actor = action.actor
        cost = passives.sp_cost(actor)
        if actor.sp < cost:
            self.log.append(f"{actor.name}: SP가 부족합니다")
            self._do_attack(action)
            return
        target = self._pick_target(action)
        if target is None:
            return
        actor.sp -= cost
        amount, critical, _ = rules.damage(
            self.balance, actor, target, skill=True, rng=self.rng
        )
        text = f"{actor.name}의 {actor.species.skill_name}! {target.name}에게 {amount}의 피해"
        if critical:
            text += " (크리티컬!)"
        text += rules.element_hint(self.balance, actor.element, target.element)
        self.log.append(text)
        self._apply_damage(actor, target, amount, physical=False)

    def _do_guard(self, action: Action) -> None:
        self.log.append(f"{action.actor.name}(은)는 방어 태세를 취했다.")

    def _do_item(self, action: Action) -> None:
        name = action.item or ""
        if self.hero.items.get(name, 0) <= 0:
            self.log.append(f"{name}(을)를 가지고 있지 않다.")
            return
        entry = self.data.items.get(name, {})
        effect = entry.get("effect")
        if not effect:
            self.log.append(f"{name}(은)는 전투 중에 쓸 수 없다.")
            return
        target = action.target or action.actor
        self.hero.take_item(name)
        if "hp" in effect and target.alive:
            healed = min(effect["hp"], target.max_hp - target.hp)
            target.hp += healed
            self.log.append(f"{name}(을)를 사용해 {target.name}의 HP를 {healed} 회복했다.")
        if "sp" in effect:
            healed = min(effect["sp"], target.max_sp - target.sp)
            target.sp += healed
            self.log.append(f"{name}(을)를 사용해 {target.name}의 SP를 {healed} 회복했다.")
        if "revive" in effect and not target.alive:
            target.hp = int(target.max_hp * effect["revive"])
            self.log.append(f"{target.name}(이)가 부활했다.")

    def _do_flee(self, action: Action) -> None:
        enemies = self.living(self.enemies)
        if not enemies:
            return
        fastest = max(enemies, key=rules.effective_speed)
        if self.rng.random() < rules.flee_chance(self.balance, action.actor, fastest):
            self.log.append("도망 성공")
            self.result = "fled"
        else:
            self.log.append("도망 실패")

    def _do_capture(self, action: Action) -> None:
        if not self.capturable:
            self.log.append("포획이 불가능한 전투입니다")
            return
        target = self._pick_target(action)
        if target is None:
            return
        if target.level > self.hero.level:
            self.log.append("주인공 레벨 부족")
            return
        ball = action.item or "몬스터볼"
        if not self.hero.take_item(ball):
            self.log.append(f"{ball}(이)가 없다.")
            return
        bonus = self.data.items.get(ball, {}).get("capture_bonus", 1.0)
        chance = rules.capture_chance(
            self.balance,
            target,
            self.hero.level,
            self.hero.element,
            ball=ball,
            ball_bonus=bonus,
            catcher=action.actor,
        )
        if self.rng.random() < chance:
            self.log.append(f"포획 성공! {target.name}(을)를 잡았다.")
            self.captured = target
            target.hp = 0
            self.result = "captured"
        else:
            self.log.append("포획 실패")

    # ------------------------------------------------------------- 종료 처리

    def _check_end(self) -> None:
        if self.finished:
            return
        if not self.living(self.enemies):
            self.result = "win"
        elif not self.living(self.allies):
            self.result = "lose"

    def _roll_drops(self) -> None:
        for enemy in self.enemies:
            if enemy.alive:
                continue
            self.gold += rules.gold_reward(self.balance, enemy)
            candidates = self.data.drops.get(enemy.species.grade, [])
            if candidates and self.rng.random() < 0.45:
                item = self.rng.choice(candidates)
                self.drops[item] = self.drops.get(item, 0) + 1

    def finish(self, *, auto: bool = False) -> list[str]:
        """전투 후 처리: 경험치 · 골드 · 드롭 · 교감도 · 허기도."""
        messages: list[str] = []
        condition = self.balance["condition"]

        if self.result in ("win", "captured"):
            total = sum(
                rules.experience_reward(self.balance, enemy, auto=auto)
                for enemy in self.enemies
                if not enemy.alive
            )
            survivors = self.living(self.allies)
            if survivors and total:
                # 경험치는 나눠 갖지 않는다. 나누면 파티를 늘릴수록 개체 성장이
                # 느려져서, 살아남기 위해 파티를 늘린 플레이어가 벌을 받는다.
                messages.append(f"전투 결과 - 경험치 {total} 획득")
                for monster in survivors:
                    messages += monster.gain_experience(total)
                # 쓰러진 몬스터도 절반은 받는다. 안 그러면 한 번 뒤처진 몬스터가
                # 매 전투 먼저 죽어 경험치를 못 받고, 영영 그 레벨에 멈춘다.
                fallen_ratio = self.balance["experience"]["fallen_ratio"]
                for monster in self.allies:
                    if not monster.alive:
                        messages += monster.gain_experience(int(total * fallen_ratio))
                messages += self.hero.gain_experience(total)
            # 승리하면 조금 회복한다. 그래야 쉬지 않고 몇 판은 이어갈 수 있다.
            ratio = condition.get("recover_after_win", 0.0)
            for monster in survivors:
                healed = min(monster.max_hp - monster.hp, int(monster.max_hp * ratio))
                monster.hp += healed
            self._roll_drops()
            if self.gold:
                self.hero.gold += self.gold
                messages.append(f"골드 {self.gold} 획득")
            for item, count in self.drops.items():
                self.hero.add_item(item, count)
                messages.append(f"{item} x{count} 획득")

        for monster in self.allies:
            messages += monster.consume_food(passives.food_ratio(monster))
            if monster.alive:
                gain = int(condition["feel_per_battle"] * passives.feel_ratio(monster))
                messages += monster.gain_feel(gain)
            else:
                monster.feel = max(0, monster.feel - condition["feel_loss_on_death"])
            monster.rage_stacks = 0
            monster.endured = False

        if self.captured is not None:
            fresh = Monster(
                self.captured.species,
                self.data,
                level=self.captured.level,
                brain=self.captured.brain,
                passives=list(self.captured.passives),
            )
            messages.append(self.hero.catch(fresh))

        for enemy in self.enemies:
            self.hero.seen.add(enemy.name)

        self.log += messages
        return messages

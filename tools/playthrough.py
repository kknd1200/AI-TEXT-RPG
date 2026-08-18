#!/usr/bin/env python3
"""플레이스루 시뮬레이터 — 실제로 한 판 끝까지 굴려 진행 속도를 잰다.

balance_check.py 는 전투 한 판만 보지만, 게임이 실제로 굴러가는지는 다른 문제다.
이 도구는 사람이 할 법한 판단(체력이 낮으면 쉰다, 갈 수 있는 가장 센 곳에 간다,
잡을 만하면 잡는다)으로 자동 플레이해서 이런 것들을 잰다.

  - 레벨 하나 올리는 데 전투 몇 번, 몇 턴이 드는가
  - 연전이 가능한가, 아니면 매번 쉬어야 하는가
  - 전멸은 얼마나 자주 나는가
  - 골드와 파티가 제때 자라는가
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tamer import network, rules, workshop                     # noqa: E402
from tamer.battle import CAPTURE, FLEE, Action, Battle         # noqa: E402
from tamer.data import load_game_data                          # noqa: E402
from tamer.models import Hero, Monster                         # noqa: E402
from tamer.world import UNKNOWN_ISLAND, build_areas, spawn     # noqa: E402

REST_THRESHOLD = 0.4          # 파티 평균 HP가 이 아래로 떨어지면 쉰다


@dataclass
class Report:
    battles: int = 0
    turns: int = 0
    wins: int = 0
    losses: int = 0
    flees: int = 0
    captures: int = 0
    rests: int = 0
    ranked: int = 0
    battles_per_level: list[int] = field(default_factory=list)
    gold_curve: list[tuple[int, int]] = field(default_factory=list)

    def summary(self, hero: Hero) -> str:
        rows = [
            f"전투 {self.battles}회 (승 {self.wins} / 패 {self.losses} / 도망 {self.flees})",
            f"포획 {self.captures}마리, 휴식 {self.rests}회, 랭킹전 {self.ranked}회",
            f"평균 {self.turns / max(1, self.battles):.1f}턴/전투",
            f"레벨당 전투 {statistics.mean(self.battles_per_level):.1f}회"
            if self.battles_per_level else "레벨업 없음",
            f"휴식 1회당 전투 {self.battles / max(1, self.rests):.1f}회",
            f"최종 Lv{hero.level} [{hero.rank}] / 골드 {hero.gold} / 파티 "
            f"{hero.used_party_points}/{hero.party_points} / 도감 {len(hero.seen)}종",
            "파티: " + ", ".join(
                f"{m.name}({m.species.grade[:4]}) Lv{m.level}" for m in hero.party
            ),
        ]
        return "\n".join("  " + row for row in rows)


def reorganize(hero: Hero) -> None:
    """파티 포인트 안에서 가장 센 조합을 꾸린다.

    사람은 좋은 몬스터를 잡으면 파티에 넣는다. 이걸 안 하면 초반에 잡은 약한
    몬스터가 파티 자리를 차지한 채 끝까지 남는다.
    """
    pool = sorted(
        hero.all_monsters,
        key=lambda m: (m.species.grade_index, m.level),
        reverse=True,
    )
    party, used = [], 0
    for monster in pool:
        if used + monster.party_cost <= hero.party_points:
            party.append(monster)
            used += monster.party_cost
    if not party:
        party = [pool[0]]
    hero.party = party
    hero.storage = [m for m in pool if m not in party]


def party_health(hero: Hero) -> float:
    alive = hero.alive_party
    if not alive:
        return 0.0
    return sum(m.hp / m.max_hp for m in alive) / len(alive)


def choose_area(hero: Hero, areas):
    """파티 전력을 크게 넘지 않는 사냥터 중 가장 높은 곳.

    사람은 자기보다 한참 센 곳에 반복해서 들어가지 않는다. 기준은 주인공 레벨이
    아니라 실제로 싸우는 몬스터의 레벨이다.
    """
    power = max((monster.level for monster in hero.party), default=hero.level)
    reachable = [
        area for area in areas
        if area.name != UNKNOWN_ISLAND and area.max_level <= power + 3
    ]
    return reachable[-1] if reachable else areas[0]


def play(seed: int, battles: int, element: str, verbose: bool = False) -> tuple[Hero, Report]:
    data = load_game_data()
    rng = random.Random(seed)
    areas = build_areas(data)
    net = network.NetworkState()

    starter_species = data.filter(element=element, grade="common")[0]
    starter = Monster(starter_species, data, level=5)
    hero = Hero(name="테스터", element=element, data=data, level=5)
    hero.party = [starter]
    hero.items = {"포션": 5, "몬스터볼": 10}
    hero.seen.add(starter.name)

    report = Report()
    level_marker, since_level = starter.level, 0

    while report.battles < battles:
        if party_health(hero) < REST_THRESHOLD or not hero.alive_party:
            for monster in hero.party:
                monster.rest()
                monster.food = data.balance["condition"]["food_max"]
            net.day += 1
            report.rests += 1
            continue

        area = choose_area(hero, areas)
        enemies = spawn(
            area, data, rng, hero.level,
            island_level=hero.island_level, party_size=len(hero.alive_party),
        )
        fight = Battle(
            data=data, hero=hero, allies=hero.alive_party, enemies=enemies, rng=rng
        )
        # 사람은 자리가 없어도 더 좋은 등급이면 일단 잡아 둔다.
        weakest_grade = min(m.species.grade_index for m in hero.party)
        want_capture = (
            hero.items.get("몬스터볼", 0) > 0
            and enemies[0].level <= hero.level
            and (
                hero.used_party_points < hero.party_points
                or enemies[0].species.grade_index > weakest_grade
            )
        )

        while not fight.finished and fight.turn < 60:
            actions = []
            danger = party_health(hero) < 0.25
            for ally in fight.living(fight.allies):
                weakest = min(fight.living(fight.enemies), key=lambda m: m.hp)
                if danger:
                    # 사람은 죽을 것 같으면 도망친다.
                    actions.append(Action(FLEE, ally))
                elif want_capture and weakest.hp <= weakest.max_hp * 0.3:
                    actions.append(Action(CAPTURE, ally, weakest, item="몬스터볼"))
                else:
                    actions.append(fight.auto_action(ally))
            fight.run_round(actions)

        fight.finish(auto=True)
        report.battles += 1
        report.turns += fight.turn
        since_level += 1
        if fight.result == "win":
            report.wins += 1
        elif fight.result == "lose":
            report.losses += 1
        elif fight.result == "captured":
            report.captures += 1
        else:
            report.flees += 1

        best = max((m.level for m in hero.party), default=level_marker)
        if best > level_marker:
            for _ in range(best - level_marker):
                report.battles_per_level.append(since_level)
            level_marker, since_level = best, 0
        report.gold_curve.append((report.battles, hero.gold))

        if verbose and report.battles % 20 == 0:
            print(f"    {report.battles:>3d}전 Lv{hero.level} 골드 {hero.gold} "
                  f"파티 {hero.used_party_points}/{hero.party_points} "
                  f"HP {party_health(hero):.0%} ({area.name})")

        # 돈이 모이면 소모품을 사고 파티를 강화한다.
        if hero.gold > 800 and hero.items.get("몬스터볼", 0) < 5:
            hero.gold -= data.items["몬스터볼"]["price"] * 5
            hero.add_item("몬스터볼", 5)
        if hero.gold > 1500 and hero.items.get("포션", 0) < 5:
            hero.gold -= data.items["포션"]["price"] * 5
            hero.add_item("포션", 5)
        if hero.gold > 3000 and hero.party:
            workshop.enhance(hero, hero.party[0], rng)
        reorganize(hero)
        # 파티 포인트를 벌기 위해 가끔 랭킹 대전을 뛴다.
        if report.battles % 10 == 0 and party_health(hero) > 0.6:
            report.ranked += 1
            rival = network.quick_rival(data, net, hero, rng)
            duel = Battle(
                data=data, hero=hero, allies=hero.alive_party,
                enemies=[Monster(m.species, data, level=m.level) for m in rival.party],
                rng=rng, capturable=False,
            )
            while not duel.finished and duel.turn < 60:
                duel.run_round([duel.auto_action(a) for a in duel.living(duel.allies)])
            duel.finish(auto=True)
            network.settle(data, net, hero, rival, "랭킹배틀", duel.result == "win")

    return hero, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battles", type=int, default=150)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    data = load_game_data()
    print(f"[플레이스루] 속성별 {args.battles}전\n")
    for element in data.elements:
        hero, report = play(args.seed, args.battles, element, verbose=args.verbose)
        print(f"{element}속성 시작")
        print(report.summary(hero))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

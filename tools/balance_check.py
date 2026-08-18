#!/usr/bin/env python3
"""밸런스 점검용 시뮬레이터.

같은 레벨/등급끼리 붙였을 때 몇 턴 만에 승부가 나는지 본다.
턴 수가 너무 적으면 커맨드 선택이 의미가 없어지므로 5~10턴을 목표로 한다.
"""

from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tamer.battle import Battle
from tamer.data import GRADE_ORDER, load_game_data
from tamer.models import Hero, Monster


def simulate(data, ally_species, enemy_species, level, trials=200, seed=0):
    rng = random.Random(seed)
    turns, wins = [], 0
    for _ in range(trials):
        hero = Hero(name="테이머", element=ally_species.element, data=data, level=level)
        ally = Monster(ally_species, data, level=level)
        enemy = Monster(enemy_species, data, level=level)
        fight = Battle(data=data, hero=hero, allies=[ally], enemies=[enemy], rng=rng)
        while not fight.finished and fight.turn < 60:
            fight.run_round([fight.auto_action(ally)])
        turns.append(fight.turn)
        wins += fight.result == "win"
    return statistics.mean(turns), wins / trials


def main() -> int:
    data = load_game_data()
    print("[같은 종 대결] 순수 TTK 측정 — 5~12턴이 목표")
    print(f"{'등급':<10}{'레벨':>5}{'평균 턴':>9}{'선공 승률':>10}")
    for grade in GRADE_ORDER:
        pool = data.filter(grade=grade)
        for level in (5, 20, 50, 80):
            species = pool[0]
            mean_turns, win_rate = simulate(data, species, species, level)
            print(f"{grade:<10}{level:>5}{mean_turns:>9.1f}{win_rate:>10.0%}")

    print("\n[상성 대결] 유리한 속성이 얼마나 이기는지")
    print(f"{'대결':<20}{'레벨':>5}{'평균 턴':>9}{'유리쪽 승률':>12}")
    for attacker, defender in (("화", "목"), ("수", "화"), ("광", "악")):
        ally = data.filter(element=attacker, grade="rare")[0]
        enemy = data.filter(element=defender, grade="rare")[0]
        for level in (20, 50):
            mean_turns, win_rate = simulate(data, ally, enemy, level)
            label = f"{ally.name}({attacker}) vs {enemy.name}({defender})"
            print(f"{label:<20}{level:>5}{mean_turns:>9.1f}{win_rate:>12.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""도감 데이터와 전투 규칙에 대한 회귀 테스트."""

import random
import unittest

from tamer import passives, rules
from tamer.battle import ATTACK, CAPTURE, GUARD, SKILL, Action, Battle
from tamer.data import GRADE_ORDER, load_game_data
from tamer.models import Hero, Learned, Monster


class DataTest(unittest.TestCase):
    def setUp(self):
        self.data = load_game_data()

    def test_roster_shape(self):
        """6속성 × 22종 = 132종."""
        self.assertEqual(len(self.data.species), 132)
        self.assertEqual(len(self.data.elements), 6)
        for element in self.data.elements:
            self.assertEqual(len(self.data.filter(element=element)), 22)

    def test_grade_distribution_per_element(self):
        expected = {"common": 4, "uncommon": 5, "rare": 4, "special": 4, "legend": 3, "god": 2}
        for element in self.data.elements:
            counts = {}
            for species in self.data.filter(element=element):
                counts[species.grade] = counts.get(species.grade, 0) + 1
            self.assertEqual(counts, expected, element)

    def test_names_are_unique(self):
        names = [species.name for species in self.data.species]
        self.assertEqual(len(set(names)), len(names))

    def test_every_species_has_skill_and_stats(self):
        for species in self.data.species:
            self.assertTrue(species.skill_name, species.name)
            self.assertTrue(species.skill_description, species.name)
            self.assertEqual(len(species.base_stats), 6, species.name)
            self.assertEqual(len(species.growth), 6, species.name)
            self.assertIn(species.grade, GRADE_ORDER)

    def test_higher_grade_is_stronger(self):
        """등급이 오를수록 같은 속성의 기본 스탯 총합이 커진다."""
        for element in self.data.elements:
            totals = [
                sum(species.base_stats.values())
                for grade in GRADE_ORDER
                for species in self.data.filter(element=element, grade=grade)[:1]
            ]
            self.assertEqual(totals, sorted(totals), element)

    def test_elements_are_balanced(self):
        """속성별 god 등급 스탯 총합이 크게 벌어지지 않는다."""
        totals = {
            element: sum(
                sum(s.base_stats.values()) for s in self.data.filter(element=element, grade="god")
            )
            for element in self.data.elements
        }
        self.assertLess(max(totals.values()) / min(totals.values()), 1.15, totals)

    def test_party_cost_table(self):
        expected = {"common": 1, "uncommon": 2, "rare": 4, "special": 7, "legend": 8, "god": 9}
        self.assertEqual(self.data.balance["party_cost"], expected)

    def test_every_passive_kind_is_understood(self):
        """passives.json 의 kind 는 전부 엔진이 아는 종류여야 한다."""
        known = {
            "physical_up", "skill_up", "physical_guard", "skill_guard", "critical_up",
            "speed_up", "desperate", "rage", "guard_master", "sp_saver", "first_strike",
            "affinity", "drain", "regen", "counter", "pierce", "endure", "hunter",
            "gourmet", "bond",
        }
        for passive in self.data.passives:
            self.assertIn(passive.kind, known, passive.name)
            self.assertTrue(passive.materials, passive.name)

    def test_every_passive_material_is_a_real_item(self):
        for passive in self.data.passives:
            for material in passive.materials:
                self.assertIn(material, self.data.items, f"{passive.name}: {material}")


class StatTest(unittest.TestCase):
    def setUp(self):
        self.data = load_game_data()
        self.sample = self.data.species[0].name

    def test_stats_grow_with_level(self):
        low = Monster(self.data.by_name(self.sample), self.data, level=1)
        high = Monster(self.data.by_name(self.sample), self.data, level=40)
        for key in ("str", "dex", "mstr", "int", "con", "spd"):
            self.assertGreater(high.stat(key), low.stat(key), key)
        self.assertGreater(high.max_hp, low.max_hp)

    def test_brain_raises_stats(self):
        plain = Monster(self.data.by_name(self.sample), self.data, level=20)
        smart = Monster(self.data.by_name(self.sample), self.data, level=20, brain=30)
        self.assertGreater(smart.stat("str"), plain.stat("str"))

    def test_starving_lowers_stats(self):
        fed = Monster(self.data.by_name(self.sample), self.data, level=20)
        hungry = Monster(self.data.by_name(self.sample), self.data, level=20, food=0)
        self.assertLess(hungry.stat("str"), fed.stat("str"))

    def test_evolution_at_max_feel(self):
        monster = Monster(self.data.by_name(self.sample), self.data, level=20)
        before = monster.stat("str")
        log = monster.gain_feel(self.data.balance["condition"]["feel_max"])
        self.assertTrue(monster.evolved)
        self.assertEqual(monster.feel, 0)
        self.assertGreater(monster.stat("str"), before)
        self.assertEqual(monster.slot_limit, self.data.slots["evolved"])
        self.assertTrue(log)

    def test_level_up_consumes_experience(self):
        monster = Monster(self.data.by_name(self.sample), self.data, level=1)
        log = monster.gain_experience(10_000)
        self.assertGreater(monster.level, 1)
        self.assertTrue(log)
        self.assertEqual(monster.hp, monster.max_hp)


class RuleTest(unittest.TestCase):
    def setUp(self):
        self.data = load_game_data()
        self.balance = self.data.balance

    def fire(self, level=20, **kwargs):
        return Monster(self.data.filter(element="화")[0], self.data, level=level, **kwargs)

    def wood(self, level=20, **kwargs):
        return Monster(self.data.filter(element="목")[0], self.data, level=level, **kwargs)

    def test_element_chart_is_symmetric(self):
        strong = self.balance["element_chart"]["strong_against"]
        for attacker, targets in strong.items():
            for defender in targets:
                self.assertGreater(rules.element_multiplier(self.balance, attacker, defender), 1.0)
                if attacker not in strong.get(defender, []):
                    self.assertLess(
                        rules.element_multiplier(self.balance, defender, attacker), 1.0
                    )

    def test_light_and_dark_are_strong_to_each_other(self):
        self.assertGreater(rules.element_multiplier(self.balance, "광", "악"), 1.0)
        self.assertGreater(rules.element_multiplier(self.balance, "악", "광"), 1.0)

    def test_skill_gets_the_full_element_bonus_physical_only_part(self):
        """스킬은 상성 배율을 그대로, 물리는 physical_weight 만큼만 받는다."""
        rng = random.Random(0)
        _, _, physical = rules.damage(
            self.balance, self.fire(), self.wood(), skill=False, rng=rng
        )
        _, _, skill = rules.damage(self.balance, self.fire(), self.wood(), skill=True, rng=rng)
        self.assertGreater(skill, physical)
        self.assertGreater(physical, 1.0)
        weight = self.balance["element_chart"]["physical_weight"]
        self.assertAlmostEqual(physical, 1.0 + (skill - 1.0) * weight)

    def test_damage_never_below_minimum(self):
        rng = random.Random(1)
        weak = Monster(self.data.filter(grade="common")[0], self.data, level=1)
        tough = Monster(self.data.filter(grade="god")[0], self.data, level=90)
        amount, _, _ = rules.damage(self.balance, weak, tough, skill=False, rng=rng)
        self.assertGreaterEqual(amount, self.balance["damage"]["minimum_damage"])

    def test_capture_requires_hero_level(self):
        target = self.wood(level=30)
        self.assertEqual(rules.capture_chance(self.balance, target, 10, "목"), 0.0)
        self.assertGreater(rules.capture_chance(self.balance, target, 30, "목"), 0.0)

    def test_capture_improves_as_hp_drops(self):
        healthy, hurt = self.wood(level=10), self.wood(level=10)
        hurt.hp = 1
        self.assertGreater(
            rules.capture_chance(self.balance, hurt, 20, "화"),
            rules.capture_chance(self.balance, healthy, 20, "화"),
        )

    def test_better_ball_improves_capture(self):
        target = self.wood(level=10)
        self.assertGreater(
            rules.capture_chance(self.balance, target, 20, "화", ball_bonus=3.0),
            rules.capture_chance(self.balance, target, 20, "화", ball_bonus=1.0),
        )

    def test_higher_grade_is_harder_to_capture(self):
        common = Monster(self.data.filter(grade="common")[0], self.data, level=10)
        god = Monster(self.data.filter(grade="god")[0], self.data, level=10)
        common.hp = god.hp = 1
        self.assertGreater(
            rules.capture_chance(self.balance, common, 20, "화"),
            rules.capture_chance(self.balance, god, 20, "화"),
        )

    def test_auto_battle_gives_less_experience(self):
        target = self.wood(level=10)
        self.assertLess(
            rules.experience_reward(self.balance, target, auto=True),
            rules.experience_reward(self.balance, target, auto=False),
        )


class PassiveEffectTest(unittest.TestCase):
    def setUp(self):
        self.data = load_game_data()
        self.balance = self.data.balance

    def monster(self, element="화", grade="rare", level=20, learned=()):
        species = self.data.filter(element=element, grade=grade)[0]
        return Monster(species, self.data, level=level, passives=list(learned))

    def test_attack_passive_raises_damage(self):
        plain = self.monster()
        buffed = self.monster(learned=[Learned("strike", 3)])
        target = self.monster(element="수")
        base, _, _ = rules.damage(self.balance, plain, target, skill=False, rng=random.Random(4))
        boosted, _, _ = rules.damage(self.balance, buffed, target, skill=False, rng=random.Random(4))
        self.assertGreater(boosted, base)

    def test_guard_passive_lowers_damage(self):
        attacker = self.monster()
        plain = self.monster(element="수")
        armored = self.monster(element="수", learned=[Learned("ironhide", 3)])
        base, _, _ = rules.damage(self.balance, attacker, plain, skill=False, rng=random.Random(4))
        reduced, _, _ = rules.damage(self.balance, attacker, armored, skill=False, rng=random.Random(4))
        self.assertLess(reduced, base)

    def test_desperate_only_applies_at_low_hp(self):
        monster = self.monster(learned=[Learned("desperate", 3)])
        self.assertEqual(passives.attack_multiplier(monster, skill=False, advantaged=False), 1.0)
        monster.hp = int(monster.max_hp * 0.2)
        self.assertGreater(passives.attack_multiplier(monster, skill=False, advantaged=False), 1.0)

    def test_sp_saver_lowers_cost(self):
        plain = self.monster()
        thrifty = self.monster(learned=[Learned("thrift", 3)])
        self.assertLess(passives.sp_cost(thrifty), passives.sp_cost(plain))

    def test_speed_passive_changes_turn_order(self):
        plain = self.monster()
        quick = self.monster(learned=[Learned("haste", 3)])
        self.assertGreater(rules.effective_speed(quick), rules.effective_speed(plain))

    def test_endure_survives_a_lethal_hit(self):
        hero = Hero(name="카이", element="화", data=self.data, level=60)
        ally = self.monster(grade="common", level=5, learned=[Learned("endure", 1)])
        enemy = self.monster(element="수", grade="god", level=80)
        hero.party = [ally]
        fight = Battle(data=self.data, hero=hero, allies=[ally], enemies=[enemy], rng=random.Random(2))
        fight.run_round([Action(GUARD, ally)])
        self.assertTrue(ally.endured)
        self.assertGreaterEqual(ally.hp, 1)

    def test_hunter_improves_capture(self):
        catcher = self.monster(learned=[Learned("hunter", 3)])
        target = self.monster(element="수", grade="common", level=5)
        self.assertGreater(
            rules.capture_chance(self.balance, target, 20, "화", catcher=catcher),
            rules.capture_chance(self.balance, target, 20, "화"),
        )


class BattleTest(unittest.TestCase):
    def setUp(self):
        self.data = load_game_data()
        self.hero = Hero(name="카이", element="화", data=self.data, level=30)
        self.hero.items = {"몬스터볼": 50, "포션": 5}

    def make_battle(self, ally, enemy, seed=3):
        self.hero.party = [ally]
        return Battle(
            data=self.data, hero=self.hero, allies=[ally], enemies=[enemy], rng=random.Random(seed)
        )

    def pick(self, element, grade, level):
        return Monster(self.data.filter(element=element, grade=grade)[0], self.data, level=level)

    def test_faster_monster_acts_first(self):
        ally = self.pick("풍", "god", 40)         # 속도형 최상위
        enemy = self.pick("목", "common", 3)      # 체력형 최하위
        fight = self.make_battle(ally, enemy)
        self.assertGreater(ally.stat("spd"), enemy.stat("spd"))
        log = fight.run_round([Action(ATTACK, ally, enemy)])
        self.assertTrue(log[0].startswith(ally.name), log)

    def test_guard_reduces_incoming_damage(self):
        taken = []
        for guarding in (False, True):
            ally = self.pick("수", "common", 20)
            enemy = self.pick("풍", "god", 45)
            fight = self.make_battle(ally, enemy, seed=11)
            fight.run_round([Action(GUARD if guarding else ATTACK, ally, enemy)])
            taken.append(ally.max_hp - ally.hp)
        self.assertLess(taken[1], taken[0])

    def test_skill_consumes_sp_and_falls_back(self):
        ally = self.pick("화", "rare", 20)
        enemy = self.pick("목", "rare", 20)
        fight = self.make_battle(ally, enemy)
        before = ally.sp
        fight.run_round([Action(SKILL, ally, enemy)])
        self.assertEqual(ally.sp, before - passives.sp_cost(ally))

        ally.sp = 0
        log = fight.run_round([Action(SKILL, ally, enemy)])
        self.assertTrue(any("SP가 부족합니다" in line for line in log), log)

    def test_battle_awards_experience_gold_and_drops(self):
        ally = self.pick("악", "god", 60)
        enemy = self.pick("광", "common", 3)
        fight = self.make_battle(ally, enemy)
        for _ in range(20):
            if fight.finished:
                break
            fight.run_round([Action(ATTACK, ally, enemy)])
        self.assertEqual(fight.result, "win")
        gold_before = self.hero.gold
        fight.finish()
        self.assertGreater(self.hero.gold, gold_before)

    def test_capture_consumes_ball_and_fills_party(self):
        ally = self.pick("악", "god", 60)
        enemy = self.pick("광", "common", 3)
        fight = self.make_battle(ally, enemy)
        enemy.hp = 1
        balls_before = self.hero.items["몬스터볼"]
        for _ in range(30):
            if fight.finished:
                break
            fight.run_round([Action(CAPTURE, ally, enemy, item="몬스터볼")])
            enemy.hp = max(1, enemy.hp)
        self.assertEqual(fight.result, "captured")
        self.assertLess(self.hero.items["몬스터볼"], balls_before)
        fight.finish()
        self.assertIn(enemy.name, [m.name for m in self.hero.all_monsters])

    def test_party_point_limit_sends_monster_to_storage(self):
        hero = Hero(name="카이", element="수", data=self.data)      # 4포인트
        hero.party = [Monster(self.data.filter(grade="god")[0], self.data)]   # 9포인트
        message = hero.catch(Monster(self.data.filter(grade="common")[0], self.data))
        self.assertIn("보관함", message)
        self.assertEqual(len(hero.storage), 1)

    def test_auto_action_picks_the_harder_hitting_command(self):
        """상성만 보고 고르면 물리형이 자기 약점인 스킬을 쓴다. 기대 피해로 골라야 한다."""
        from tamer import rules as rule_module

        for element in ("화", "광"):
            ally = self.pick(element, "rare", 20)
            enemy = self.pick("목", "rare", 20)
            fight = self.make_battle(ally, enemy)
            chosen = fight.auto_action(ally).kind
            physical = rule_module.estimate_damage(self.data.balance, ally, enemy, skill=False)
            skill = rule_module.estimate_damage(self.data.balance, ally, enemy, skill=True)
            self.assertEqual(chosen, SKILL if skill > physical else ATTACK, element)

    def test_enemy_never_targets_its_own_side(self):
        """스탯이 같은 두 마리가 붙어도 적이 자기 편을 때리면 안 된다."""
        species = self.data.filter(grade="rare")[0]
        ally = Monster(species, self.data, level=20)
        enemy = Monster(species, self.data, level=20)
        fight = self.make_battle(ally, enemy, seed=7)
        for _ in range(4):
            if fight.finished:
                break
            fight.run_round([Action(GUARD, ally)])
        self.assertLess(ally.hp, ally.max_hp)      # 적은 반드시 아군을 때린다
        self.assertEqual(enemy.hp, enemy.max_hp)   # 아군은 방어만 했다


if __name__ == "__main__":
    unittest.main()

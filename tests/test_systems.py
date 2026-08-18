"""공방 · 네트워크 · 저장 기능 테스트."""

import random
import tempfile
import unittest
from pathlib import Path

from tamer import network, save, workshop
from tamer.data import GRADE_ORDER, load_game_data
from tamer.models import Hero, Learned, Monster
from tamer.network import NetworkState


class Fixture(unittest.TestCase):
    def setUp(self):
        self.data = load_game_data()
        self.hero = Hero(name="카이", element="화", data=self.data, level=20, gold=100_000)
        self.rng = random.Random(0)

    def pick(self, grade="common", element="화", level=10, **kwargs):
        species = self.data.filter(element=element, grade=grade)
        return Monster(species[kwargs.pop("slot", 0)], self.data, level=level, **kwargs)


class FusionTest(Fixture):
    def test_same_grade_required(self):
        first = self.pick("common")
        second = self.pick("uncommon")
        self.hero.party = [first, second]
        outcome = workshop.fuse(self.hero, first, second, self.rng)
        self.assertFalse(outcome.ok)
        self.assertIn("같은 등급", outcome.messages[0])

    def test_god_cannot_be_fused(self):
        first, second = self.pick("god"), self.pick("god", slot=1)
        self.hero.party = [first, second]
        self.assertFalse(workshop.fuse(self.hero, first, second, self.rng).ok)

    def test_success_produces_higher_grade_and_eats_materials(self):
        first, second = self.pick("common"), self.pick("common", slot=1)
        self.hero.party = [first, second]
        outcome = workshop.fuse(self.hero, first, second, random.Random(1))
        self.assertTrue(outcome.ok)
        self.assertIsNotNone(outcome.monster)
        self.assertEqual(outcome.monster.species.grade, "uncommon")
        self.assertNotIn(first, self.hero.all_monsters)
        self.assertNotIn(second, self.hero.all_monsters)

    def test_failure_drops_a_grade(self):
        """rare 조합에 실패하면 uncommon 이 나온다."""
        results = []
        for seed in range(40):
            hero = Hero(name="카이", element="화", data=self.data, gold=100_000)
            first, second = self.pick("rare"), self.pick("rare", slot=1)
            hero.party = [first, second]
            outcome = workshop.fuse(hero, first, second, random.Random(seed))
            results.append(outcome.monster.species.grade)
        self.assertIn("special", results)
        self.assertIn("uncommon", results)

    def test_lowest_grade_failure_stays_common(self):
        for seed in range(30):
            hero = Hero(name="카이", element="화", data=self.data, gold=100_000)
            first, second = self.pick("common"), self.pick("common", slot=1)
            hero.party = [first, second]
            outcome = workshop.fuse(hero, first, second, random.Random(seed))
            self.assertIn(outcome.monster.species.grade, ("common", "uncommon"))

    def test_catalyst_raises_success_rate(self):
        plain = workshop.fusion_rate(self.data, "rare")
        boosted = workshop.fusion_rate(self.data, "rare", catalyst=True)
        self.assertGreater(boosted, plain)

    def test_passives_can_be_inherited(self):
        found = False
        for seed in range(30):
            hero = Hero(name="카이", element="화", data=self.data, gold=100_000)
            first = self.pick("common", passives=[Learned("strike", 2)])
            second = self.pick("common", slot=1, passives=[Learned("haste", 1)])
            hero.party = [first, second]
            outcome = workshop.fuse(hero, first, second, random.Random(seed))
            if outcome.monster.passives:
                found = True
                for learned in outcome.monster.passives:
                    self.assertIn(learned.passive_id, ("strike", "haste"))
        self.assertTrue(found, "패시브가 한 번도 계승되지 않았다")

    def test_cost_is_charged(self):
        first, second = self.pick("common"), self.pick("common", slot=1)
        self.hero.party = [first, second]
        before = self.hero.gold
        workshop.fuse(self.hero, first, second, random.Random(1))
        self.assertEqual(before - self.hero.gold, workshop.fusion_cost(self.data, "common"))


class EnhanceTest(Fixture):
    def test_success_raises_brain(self):
        monster = self.pick()
        self.hero.party = [monster]
        outcome = workshop.enhance(self.hero, monster, random.Random(1))
        self.assertTrue(outcome.ok)
        self.assertEqual(monster.brain, 1)

    def test_rate_falls_as_brain_rises(self):
        low = self.pick()
        high = self.pick(brain=50)
        self.assertGreater(
            workshop.enhance_rate(self.data, low), workshop.enhance_rate(self.data, high)
        )

    def test_rate_never_below_floor(self):
        monster = self.pick(brain=98)
        self.assertGreaterEqual(
            workshop.enhance_rate(self.data, monster), self.data.balance["enhance"]["min_rate"]
        )

    def test_gold_is_required(self):
        poor = Hero(name="빈털터리", element="화", data=self.data, gold=0)
        monster = self.pick()
        poor.party = [monster]
        self.assertFalse(workshop.enhance(poor, monster, self.rng).ok)


class PassiveAttachTest(Fixture):
    def stock(self, passive_id):
        for name, count in self.data.passive(passive_id).materials.items():
            self.hero.add_item(name, count * 8)

    def test_attach_consumes_materials_and_gold(self):
        monster = self.pick()
        self.stock("strike")
        gold_before = self.hero.gold
        outcome = workshop.attach_passive(self.hero, monster, "strike")
        self.assertTrue(outcome.ok)
        self.assertTrue(monster.has_passive("strike"))
        self.assertLess(self.hero.gold, gold_before)

    def test_missing_materials_blocks_attach(self):
        monster = self.pick()
        outcome = workshop.attach_passive(self.hero, monster, "strike")
        self.assertFalse(outcome.ok)
        self.assertIn("재료", outcome.messages[0])

    def test_same_passive_levels_up_without_new_slot(self):
        monster = self.pick()
        self.stock("strike")
        workshop.attach_passive(self.hero, monster, "strike")
        workshop.attach_passive(self.hero, monster, "strike")
        self.assertEqual(len(monster.passives), 1)
        self.assertEqual(monster.passive_level("strike"), 2)

    def test_cannot_exceed_max_level(self):
        monster = self.pick()
        self.stock("strike")
        for _ in range(5):
            workshop.attach_passive(self.hero, monster, "strike")
        self.assertEqual(monster.passive_level("strike"), self.data.passive("strike").max_level)

    def test_slot_limit_is_enforced_and_grows_on_evolution(self):
        monster = self.pick()
        for passive in self.data.passives:
            self.stock(passive.id)
        attached = []
        for passive in self.data.passives:
            if workshop.attach_passive(self.hero, monster, passive.id).ok:
                attached.append(passive.id)
        self.assertEqual(len(attached), self.data.slots["base"])

        monster.gain_feel(self.data.balance["condition"]["feel_max"])
        self.assertTrue(monster.evolved)
        extra = [
            passive.id
            for passive in self.data.passives
            if not monster.has_passive(passive.id)
            and workshop.attach_passive(self.hero, monster, passive.id).ok
        ]
        self.assertEqual(len(monster.passives), self.data.slots["evolved"])
        self.assertTrue(extra)


class NetworkTest(Fixture):
    def setUp(self):
        super().setUp()
        self.state = NetworkState()
        self.hero.party = [self.pick()]

    def test_rivals_are_deterministic_per_day(self):
        first = network.find_rivals(self.data, self.state, self.hero)
        second = network.find_rivals(self.data, self.state, self.hero)
        self.assertEqual([r.name for r in first], [r.name for r in second])
        self.state.day += 1
        third = network.find_rivals(self.data, self.state, self.hero)
        self.assertNotEqual([r.name for r in first], [r.name for r in third])

    def test_ranking_battle_moves_rank_points(self):
        rival = network.find_rivals(self.data, self.state, self.hero)[0]
        before = self.hero.rank_points
        network.settle(self.data, self.state, self.hero, rival, "랭킹배틀", True)
        self.assertGreater(self.hero.rank_points, before)
        network.settle(self.data, self.state, self.hero, rival, "랭킹배틀", False)
        self.assertLess(self.hero.rank_points, before + self.data.balance["network"]["rank_point_win"])

    def test_friendly_battle_does_not_move_rank_points(self):
        rival = network.find_rivals(self.data, self.state, self.hero)[0]
        before = self.hero.rank_points
        network.settle(self.data, self.state, self.hero, rival, "친선배틀", True)
        self.assertEqual(self.hero.rank_points, before)
        self.assertEqual(self.hero.wins, 1)

    def test_battle_log_is_capped(self):
        rival = network.find_rivals(self.data, self.state, self.hero)[0]
        for _ in range(40):
            network.settle(self.data, self.state, self.hero, rival, "퀵배틀", True)
        self.assertLessEqual(len(self.state.log), 20)

    def test_leaderboard_contains_the_player(self):
        rows = network.leaderboard(self.data, self.state, self.hero)
        self.assertTrue(any(name.startswith("▶") for name, _ in rows))
        self.assertEqual(rows, sorted(rows, key=lambda row: -row[1]))

    def test_market_buy_and_sell(self):
        listing = network.market_listings(self.data, self.state, self.hero)[0]
        self.hero.gold = listing.price
        network.buy(self.hero, listing)
        self.assertEqual(self.hero.gold, 0)
        self.assertIn(listing.monster.name, [m.name for m in self.hero.all_monsters])
        network.sell(self.hero, listing.monster)
        self.assertGreater(self.hero.gold, 0)

    def test_last_party_monster_cannot_be_sold(self):
        only = self.hero.party[0]
        self.hero.storage.clear()
        self.assertIn("팔 수 없다", network.sell(self.hero, only)[0])

    def test_gifts_are_once_per_day(self):
        first = network.collect_gifts(self.data, self.state, self.hero)
        self.assertTrue(any("받았다" in line for line in first))
        second = network.collect_gifts(self.data, self.state, self.hero)
        self.assertIn("이미", second[0])
        self.state.day += 1
        self.assertTrue(any("받았다" in line for line in network.collect_gifts(self.data, self.state, self.hero)))

    def test_island_level_raises_party_points(self):
        thresholds = self.data.balance["island"]["party_point_levels"]
        before = self.hero.party_points
        self.hero.island_level = thresholds[0]
        self.assertEqual(self.hero.party_points, before + 1)

    def test_visiting_gives_more_island_experience(self):
        home = Hero(name="집", element="화", data=self.data)
        away = Hero(name="방문", element="화", data=self.data)
        # 레벨업 문턱보다 작게 줘서 남은 경험치끼리 곧바로 비교한다.
        network.island_gain(self.data, home, 50, visiting=False)
        network.island_gain(self.data, away, 50, visiting=True)
        self.assertGreater(away.island_experience, home.island_experience)

    def test_island_grade_cap_opens_with_level(self):
        low = network.island_grade_cap(self.data, 1)
        high = network.island_grade_cap(self.data, 40)
        self.assertLess(low, high)
        self.assertEqual(GRADE_ORDER[high], "god")

    def test_chest_is_once_per_day(self):
        self.assertTrue(any("얻었다" in line for line in network.open_chest(self.data, self.state, self.hero)))
        self.assertIn("이미", network.open_chest(self.data, self.state, self.hero)[0])


class SaveTest(Fixture):
    def round_trip(self, hero, state, area_index=0):
        with tempfile.TemporaryDirectory() as folder:
            original = save.SAVE_DIR
            save.SAVE_DIR = Path(folder)
            try:
                path = save.write(hero, state, area_index)
                return save.read(self.data, path)
            finally:
                save.SAVE_DIR = original

    def test_round_trip_preserves_state(self):
        hero = self.hero
        hero.party = [self.pick("rare", level=33, brain=7, passives=[Learned("strike", 2)])]
        hero.storage = [self.pick("common", level=4)]
        hero.party[0].hp = 12
        hero.items = {"포션": 3, "빛조각": 1}
        hero.seen = {hero.party[0].name}
        hero.island_level = 22
        hero.wins, hero.losses = 4, 2
        state = NetworkState(day=9, last_gift_day=8)
        network.settle(self.data, state, hero, network.Rival("상대", 900, []), "퀵배틀", True)

        loaded, loaded_state, area = self.round_trip(hero, state, area_index=5)
        self.assertEqual(loaded.name, hero.name)
        self.assertEqual(loaded.gold, hero.gold)
        self.assertEqual(loaded.island_level, 22)
        self.assertEqual(loaded.items, hero.items)
        self.assertEqual(loaded.seen, hero.seen)
        self.assertEqual(area, 5)
        self.assertEqual(loaded_state.day, 9)
        self.assertEqual(len(loaded_state.log), 1)

        saved_monster = loaded.party[0]
        self.assertEqual(saved_monster.level, 33)
        self.assertEqual(saved_monster.brain, 7)
        self.assertEqual(saved_monster.hp, 12)
        self.assertEqual(saved_monster.passive_level("strike"), 2)
        self.assertEqual(len(loaded.storage), 1)

    def test_evolved_monster_survives_round_trip(self):
        hero = self.hero
        monster = self.pick("rare", level=20)
        monster.gain_feel(self.data.balance["condition"]["feel_max"])
        hero.party = [monster]
        loaded, _, _ = self.round_trip(hero, NetworkState())
        self.assertTrue(loaded.party[0].evolved)
        self.assertEqual(loaded.party[0].slot_limit, self.data.slots["evolved"])

    def test_unknown_format_is_rejected(self):
        payload = save.to_dict(self.hero, NetworkState())
        payload["format"] = 999
        with self.assertRaises(save.SaveError):
            save.from_dict(self.data, payload)

    def test_unknown_monster_is_reported(self):
        self.hero.party = [self.pick()]
        payload = save.to_dict(self.hero, NetworkState())
        payload["hero"]["party"][0]["species"] = "존재하지않는몬스터"
        with self.assertRaises(save.SaveError):
            save.from_dict(self.data, payload)


if __name__ == "__main__":
    unittest.main()

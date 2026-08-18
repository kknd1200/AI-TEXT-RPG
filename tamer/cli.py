"""텍스트 UI."""

from __future__ import annotations

import random

from tamer import network, save, workshop
from tamer.battle import ATTACK, CAPTURE, FLEE, GUARD, ITEM, SKILL, Action, Battle
from tamer.data import GRADE_ORDER, GameData, load_game_data
from tamer.models import Hero, Monster
from tamer.network import NetworkState
from tamer.world import UNKNOWN_ISLAND, Area, build_areas, spawn

RULE = "─" * 66
TITLE = "엘리멘탈 테이머"


class Quit(Exception):
    """입력이 끊기면(EOF, Ctrl-D) 조용히 게임을 끝낸다."""


def prompt(message: str, options: list[str], reader) -> int:
    """옵션을 번호로 고르게 한다. 잘못 입력하면 다시 묻는다."""
    while True:
        print(message)
        for index, option in enumerate(options, 1):
            print(f"  {index}. {option}")
        try:
            raw = reader("> ").strip()
        except EOFError as error:
            raise Quit from error
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("잘못된 입력입니다.\n")


def ask_text(message: str, reader) -> str:
    try:
        return reader(message).strip()
    except EOFError as error:
        raise Quit from error


class Game:
    def __init__(self, data: GameData, rng: random.Random, reader=input):
        self.data = data
        self.rng = rng
        self.reader = reader
        self.areas = build_areas(data)
        self.hero: Hero | None = None
        self.net = NetworkState()
        self.area_index = 0

    # ------------------------------------------------------------ 시작 처리

    def title_screen(self) -> None:
        print(RULE)
        print(f"{TITLE} — 텍스트 RPG")
        print(RULE)
        saves = save.list_saves()
        options = ["새로 시작하기"] + ([f"불러오기 ({len(saves)}개)"] if saves else [])
        if prompt("", options, self.reader) == 1:
            if self.load_game():
                return
        self.create_hero()

    def create_hero(self) -> None:
        name = ask_text("테이머 이름 (그냥 엔터 = 카이): ", self.reader) or "카이"
        elements = self.data.elements
        picked = prompt(
            "\n자기 속성을 고른다. 같은 속성 몬스터는 포획 확률과 교감도가 유리하다.",
            [f"{element}속성" for element in elements],
            self.reader,
        )
        hero = Hero(name=name, element=elements[picked], data=self.data)
        hero.items = {"포션": 5, "몬스터볼": 5, "에테르": 2}

        starters = self.data.filter(element=hero.element, grade="common")
        choice = prompt(
            "\n첫 파트너를 고른다.",
            [f"{s.name} - {s.skill_name}({s.skill_description})" for s in starters],
            self.reader,
        )
        starter = Monster(starters[choice], self.data, level=5)
        # 포획은 자기 레벨 이하만 가능하다. 첫 파트너와 같은 레벨에서 출발한다.
        hero.level = starter.level
        hero.party.append(starter)
        hero.seen.add(starter.name)
        self.hero = hero
        print(f"\n{name}(은)는 {starter.name}(와)과 함께 길을 나섰다.\n")

    # -------------------------------------------------------------- 메인 루프

    def run(self) -> None:
        self.title_screen()
        while True:
            hero = self.hero
            assert hero is not None
            print(RULE)
            print(
                f"{hero.name} [{hero.rank}] Lv{hero.level}  {hero.element}속성  "
                f"골드 {hero.gold}  파티 {hero.used_party_points}/{hero.party_points}  "
                f"RP {hero.rank_points} ({hero.wins}승 {hero.losses}패)  "
                f"섬 Lv{hero.island_level}  {self.net.day}일차"
            )
            choice = prompt(
                "무엇을 할까?",
                [
                    "사냥하기",
                    "파티 · 도감",
                    "공방 (조합 · 강화 · 패시브)",
                    "배틀존",
                    "몬스터마트",
                    "우체통",
                    "미지의 섬",
                    "상점",
                    "쉬기 (다음 날로)",
                    "저장하기",
                    "종료",
                ],
                self.reader,
            )
            handlers = [
                self.hunt, self.party_menu, self.workshop_menu, self.battle_zone,
                self.market_menu, self.mailbox_menu, self.island_menu, self.shop_menu,
                self.rest,
            ]
            if choice < len(handlers):
                handlers[choice]()
            elif choice == len(handlers):
                self.save_game()
            else:
                print("게임을 종료한다.")
                return

    # ------------------------------------------------------------ 저장/휴식

    def save_game(self) -> None:
        assert self.hero is not None
        path = save.write(self.hero, self.net, self.area_index)
        print(f"{path} 에 저장했다.\n")

    def load_game(self) -> bool:
        saves = save.list_saves()
        if not saves:
            print("저장 파일이 없다.\n")
            return False
        index = prompt(
            "\n어느 기록을 불러올까?",
            [path.stem for path in saves] + ["돌아가기"],
            self.reader,
        )
        if index == len(saves):
            return False
        try:
            self.hero, self.net, self.area_index = save.read(self.data, saves[index])
        except save.SaveError as error:
            print(f"불러오기 실패: {error}\n")
            return False
        print(f"{self.hero.name}의 기록을 불러왔다.\n")
        return True

    def rest(self) -> None:
        assert self.hero is not None
        for monster in self.hero.party:
            monster.rest()
            monster.food = self.data.balance["condition"]["food_max"]
        self.net.day += 1
        print(f"하룻밤 쉬었다. 파티가 전부 회복했다. ({self.net.day}일차)\n")

    # ------------------------------------------------------------ 파티/도감

    def party_menu(self) -> None:
        assert self.hero is not None
        while True:
            print("\n[파티]")
            for monster in self.hero.party:
                print("  " + monster.status_line())
            if self.hero.storage:
                print("[보관함]")
                for monster in self.hero.storage:
                    print("  " + monster.status_line())
            choice = prompt(
                "",
                ["파티 편성", "먹이 주기", "도감 보기", "돌아가기"],
                self.reader,
            )
            if choice == 0:
                self.organize_party()
            elif choice == 1:
                self.feed_menu()
            elif choice == 2:
                self.show_book()
            else:
                return

    def organize_party(self) -> None:
        assert self.hero is not None
        hero = self.hero
        pool = hero.party + hero.storage
        index = prompt(
            f"\n어느 몬스터를 옮길까? (파티 포인트 {hero.used_party_points}/{hero.party_points})",
            [f"{'파티' if m in hero.party else '보관'} {m.status_line()}" for m in pool] + ["돌아가기"],
            self.reader,
        )
        if index == len(pool):
            return
        monster = pool[index]
        if monster in hero.party:
            if len(hero.party) == 1:
                print("파티가 비면 사냥을 할 수 없다.\n")
                return
            hero.party.remove(monster)
            hero.storage.append(monster)
            print(f"{monster.name}(을)를 보관함으로 보냈다.\n")
        elif hero.can_add(monster):
            hero.storage.remove(monster)
            hero.party.append(monster)
            print(f"{monster.name}(을)를 파티에 넣었다.\n")
        else:
            print(f"파티 포인트가 모자란다. ({monster.party_cost} 필요)\n")

    def feed_menu(self) -> None:
        assert self.hero is not None
        marbles = [name for name in self.hero.items if name.startswith("마블-")]
        if not marbles:
            print("먹일 마블이 없다. 상점에서 살 수 있다.\n")
            return
        item = marbles[prompt("\n어떤 마블을?", [f"{m} x{self.hero.items[m]}" for m in marbles], self.reader)]
        target = self.hero.party[
            prompt("누구에게?", [m.status_line() for m in self.hero.party], self.reader)
        ]
        self.hero.take_item(item)
        for line in target.feed(item.split("-")[1]):
            print("  " + line)
        print()

    def show_book(self) -> None:
        assert self.hero is not None
        seen = sorted(self.hero.seen)
        print(f"\n[도감] {len(seen)}/{len(self.data.species)}종 확인")
        for grade in GRADE_ORDER:
            names = [s.name for s in self.data.filter(grade=grade) if s.name in self.hero.seen]
            if names:
                print(f"  {grade:<9s} {', '.join(names)}")
        print()

    # ------------------------------------------------------------ 공방

    def workshop_menu(self) -> None:
        assert self.hero is not None
        while True:
            choice = prompt(
                f"\n[공방] 골드 {self.hero.gold}",
                ["몬스터 조합", "몬스터 강화", "패시브 스킬 장착", "돌아가기"],
                self.reader,
            )
            if choice == 0:
                self.fuse_menu()
            elif choice == 1:
                self.enhance_menu()
            elif choice == 2:
                self.passive_menu()
            else:
                return

    def _choose_monster(self, message: str, pool: list[Monster]) -> Monster | None:
        if not pool:
            print("대상이 없다.\n")
            return None
        index = prompt(message, [m.status_line() for m in pool] + ["돌아가기"], self.reader)
        return None if index == len(pool) else pool[index]

    def fuse_menu(self) -> None:
        hero = self.hero
        assert hero is not None
        first = self._choose_monster("\n재료 1", hero.all_monsters)
        if first is None:
            return
        same = [m for m in hero.all_monsters if m is not first and m.species.grade == first.species.grade]
        if not same:
            print(f"{first.species.grade} 등급 짝이 없다. 조합은 같은 등급끼리만 된다.\n")
            return
        second = self._choose_monster("재료 2 (같은 등급)", same)
        if second is None:
            return
        grade = first.species.grade
        catalyst = False
        if hero.items.get("조합촉매", 0) > 0:
            catalyst = prompt(
                f"조합촉매를 쓸까? (성공률 {workshop.fusion_rate(self.data, grade):.0%}"
                f" → {workshop.fusion_rate(self.data, grade, True):.0%})",
                [f"쓴다 (x{hero.items['조합촉매']})", "안 쓴다"],
                self.reader,
            ) == 0
        print(f"\n비용 {workshop.fusion_cost(self.data, grade)} 골드")
        for line in workshop.fuse(hero, first, second, self.rng, catalyst=catalyst).messages:
            print("  " + line)
        print()

    def enhance_menu(self) -> None:
        hero = self.hero
        assert hero is not None
        monster = self._choose_monster("\n어느 몬스터를 강화할까?", hero.all_monsters)
        if monster is None:
            return
        catalyst = False
        if hero.items.get("강화촉매", 0) > 0:
            catalyst = prompt(
                f"강화촉매를 쓸까? (성공률 {workshop.enhance_rate(self.data, monster):.0%}"
                f" → {workshop.enhance_rate(self.data, monster, True):.0%})",
                [f"쓴다 (x{hero.items['강화촉매']})", "안 쓴다"],
                self.reader,
            ) == 0
        print(f"\n비용 {workshop.enhance_cost(self.data, monster)} 골드")
        for line in workshop.enhance(hero, monster, self.rng, catalyst=catalyst).messages:
            print("  " + line)
        print()

    def passive_menu(self) -> None:
        hero = self.hero
        assert hero is not None
        monster = self._choose_monster("\n어느 몬스터에게?", hero.all_monsters)
        if monster is None:
            return
        options, labels = [], []
        for passive in self.data.passives:
            level = monster.passive_level(passive.id)
            if level >= passive.max_level:
                continue
            gold, materials = workshop.attach_cost(self.data, monster, passive.id)
            need = ", ".join(f"{name} {count}" for name, count in materials.items())
            state = f"Lv{level}→{level + 1}" if level else "신규"
            labels.append(f"{passive.name} [{state}] {passive.description} — {gold}G, {need}")
            options.append(passive.id)
        if not options:
            print("더 배울 패시브가 없다.\n")
            return
        print(f"\n슬롯 {len(monster.passives)}/{monster.slot_limit}"
              f"  보유 재료: {', '.join(f'{k} x{v}' for k, v in hero.items.items()) or '없음'}")
        index = prompt("어떤 패시브를?", labels + ["돌아가기"], self.reader)
        if index == len(options):
            return
        for line in workshop.attach_passive(hero, monster, options[index]).messages:
            print("  " + line)
        print()

    # ------------------------------------------------------------ 상점

    def shop_menu(self) -> None:
        hero = self.hero
        assert hero is not None
        sellable = [
            (name, entry) for name, entry in self.data.items.items()
            if entry["category"] in ("소비", "볼", "보조", "먹이")
        ]
        while True:
            index = prompt(
                f"\n[상점] 골드 {hero.gold}",
                [f"{name} — {entry['price']}G ({entry['category']})" for name, entry in sellable]
                + ["돌아가기"],
                self.reader,
            )
            if index == len(sellable):
                return
            name, entry = sellable[index]
            if hero.gold < entry["price"]:
                print("골드가 모자란다.\n")
                continue
            hero.gold -= entry["price"]
            hero.add_item(name)
            print(f"{name}(을)를 샀다. (보유 {hero.items[name]})\n")

    # ------------------------------------------------------------ 배틀존

    def battle_zone(self) -> None:
        hero = self.hero
        assert hero is not None
        while True:
            choice = prompt(
                f"\n[배틀존] RP {hero.rank_points}  {hero.wins}승 {hero.losses}패",
                ["퀵배틀", "랭킹배틀", "친선배틀", "챌린지", "랭킹판", "배틀로그", "돌아가기"],
                self.reader,
            )
            if choice == 0:
                self.versus(network.quick_rival(self.data, self.net, hero, self.rng), "퀵배틀")
            elif choice in (1, 2):
                mode = "랭킹배틀" if choice == 1 else "친선배틀"
                rivals = network.find_rivals(self.data, self.net, hero)
                index = prompt(
                    f"\n{mode} 상대를 고른다.",
                    [rival.describe() for rival in rivals] + ["돌아가기"],
                    self.reader,
                )
                if index < len(rivals):
                    self.versus(rivals[index], mode)
            elif choice == 3:
                self.challenge()
            elif choice == 4:
                print()
                for rank, (name, points) in enumerate(
                    network.leaderboard(self.data, self.net, hero), 1
                ):
                    print(f"  {rank:>2d}. {name:<16s} {points}")
                print()
            elif choice == 5:
                print("\n[배틀로그]")
                for record in reversed(self.net.log[-10:]):
                    print(f"  {record.day}일차 {record.mode:<6s} vs {record.opponent:<16s} "
                          f"{record.result} ({record.rank_delta:+d})")
                if not self.net.log:
                    print("  기록이 없다.")
                print()
            else:
                return

    def versus(self, rival: network.Rival, mode: str) -> bool:
        hero = self.hero
        assert hero is not None
        if not hero.alive_party:
            print("싸울 수 있는 몬스터가 없다.\n")
            return False
        print(f"\n{mode}: {rival.describe()}")
        fight = Battle(
            data=self.data,
            hero=hero,
            allies=hero.alive_party,
            enemies=[
                Monster(m.species, self.data, level=m.level, brain=m.brain) for m in rival.party
            ],
            rng=self.rng,
            capturable=False,
        )
        self.battle_loop(fight)
        won = fight.result in ("win", "captured")
        for line in network.settle(self.data, self.net, hero, rival, mode, won):
            print("  " + line)
        print()
        return won

    def challenge(self) -> None:
        hero = self.hero
        assert hero is not None
        rounds = self.data.balance["network"]["challenge_rounds"]
        print(f"\n챌린지: {rounds}연전. 도중에 지면 끝난다.")
        for step in range(rounds):
            print(f"\n── {step + 1}/{rounds} 전 ──")
            rival = network.quick_rival(self.data, self.net, hero, self.rng)
            if not self.versus(rival, "챌린지"):
                print("챌린지 실패.\n")
                return
        reward = self.rng.choice(["마스터볼", "강화촉매", "조합촉매"])
        hero.add_item(reward, 2)
        print(f"챌린지 완주! 보상으로 {reward} x2 를 받았다.\n")

    # ------------------------------------------------------------ 마트/우체통

    def market_menu(self) -> None:
        hero = self.hero
        assert hero is not None
        while True:
            choice = prompt(
                f"\n[몬스터마트] 골드 {hero.gold}",
                ["몬스터 사기", "몬스터 팔기", "돌아가기"],
                self.reader,
            )
            if choice == 0:
                listings = network.market_listings(self.data, self.net, hero)
                index = prompt(
                    "\n매물 (하루에 한 번 바뀐다)",
                    [
                        f"{l.monster.status_line()}  {l.price}G  ({l.seller})"
                        for l in listings
                    ] + ["돌아가기"],
                    self.reader,
                )
                if index < len(listings):
                    for line in network.buy(hero, listings[index]):
                        print("  " + line)
                    print()
            elif choice == 1:
                monster = self._choose_monster("\n누구를 팔까?", hero.all_monsters)
                if monster is not None:
                    for line in network.sell(hero, monster):
                        print("  " + line)
                    print()
            else:
                return

    def mailbox_menu(self) -> None:
        hero = self.hero
        assert hero is not None
        while True:
            choice = prompt("\n[우체통]", ["선물 받기", "아이템 보내기", "돌아가기"], self.reader)
            if choice == 0:
                for line in network.collect_gifts(self.data, self.net, hero):
                    print("  " + line)
                print()
            elif choice == 1:
                names = sorted(hero.items)
                if not names:
                    print("보낼 아이템이 없다.\n")
                    continue
                index = prompt(
                    "무엇을 보낼까?",
                    [f"{name} x{hero.items[name]}" for name in names] + ["돌아가기"],
                    self.reader,
                )
                if index < len(names):
                    for line in network.send_gift(hero, names[index]):
                        print("  " + line)
                    print()
            else:
                return

    # ------------------------------------------------------------ 미지의 섬

    def island_menu(self) -> None:
        hero = self.hero
        assert hero is not None
        island = next(area for area in self.areas if area.name == UNKNOWN_ISLAND)
        while True:
            choice = prompt(
                f"\n[미지의 섬] 섬 Lv{hero.island_level} (경험치 {hero.island_experience})",
                ["내 섬에서 사냥", "친구의 섬 방문", "보물상자 열기", "돌아가기"],
                self.reader,
            )
            if choice == 0:
                self.hunt_at(island, visiting=False)
            elif choice == 1:
                friends = network.friend_islands(self.data, self.net, hero)
                index = prompt(
                    "\n누구의 섬에 갈까? (남의 섬은 경험치를 더 준다)",
                    [f"{name} — 섬 Lv{level}" for name, level in friends] + ["돌아가기"],
                    self.reader,
                )
                if index < len(friends):
                    self.hunt_at(island, visiting=True, island_level=friends[index][1])
            elif choice == 2:
                for line in network.open_chest(self.data, self.net, hero):
                    print("  " + line)
                print()
            else:
                return

    # ------------------------------------------------------------------ 사냥

    def hunt(self) -> None:
        hero = self.hero
        assert hero is not None
        available = [
            area for area in self.areas
            if area.name != UNKNOWN_ISLAND and area.min_level <= hero.level + 6
        ]
        index = prompt(
            "\n어디로 갈까?",
            [area.describe() for area in available] + ["돌아가기"],
            self.reader,
        )
        if index == len(available):
            return
        self.area_index = index
        self.hunt_at(available[index], visiting=False)

    def hunt_at(self, area: Area, *, visiting: bool, island_level: int | None = None) -> None:
        hero = self.hero
        assert hero is not None
        if not hero.alive_party:
            print("싸울 수 있는 몬스터가 없다. 쉬어야 한다.\n")
            return
        level = island_level if island_level is not None else hero.island_level
        enemies = spawn(area, self.data, self.rng, hero.level, island_level=level)
        fight = Battle(
            data=self.data, hero=hero, allies=hero.alive_party, enemies=enemies, rng=self.rng
        )
        self.battle_loop(fight)
        if area.name == UNKNOWN_ISLAND and fight.result in ("win", "captured"):
            gain = sum(enemy.level for enemy in enemies) * 3
            for line in network.island_gain(self.data, hero, gain, visiting=visiting):
                print("  " + line)
        for line in hero.promote():
            print("  " + line)

    def battle_loop(self, fight: Battle) -> None:
        names = " / ".join(f"{enemy.name} Lv{enemy.level}" for enemy in fight.enemies)
        print(f"\n{names} (이)가 나타났다!\n")
        auto = False

        while not fight.finished:
            print(RULE)
            for enemy in fight.enemies:
                state = f"HP {enemy.hp}/{enemy.max_hp}" if enemy.alive else "쓰러짐"
                print(f"  [적]   {enemy.name} Lv{enemy.level} {enemy.element} {state}")
            for ally in fight.allies:
                state = f"HP {ally.hp}/{ally.max_hp} SP {ally.sp}/{ally.max_sp}"
                print(f"  [아군] {ally.name} Lv{ally.level} {ally.element} {state}")

            actions = []
            for ally in fight.living(fight.allies):
                if auto:
                    actions.append(fight.auto_action(ally))
                    continue
                action = self.ask_command(fight, ally)
                if action is None:          # 자동 전투로 전환
                    auto = True
                    action = fight.auto_action(ally)
                actions.append(action)

            for line in fight.run_round(actions):
                print("  " + line)
            print()

        for line in fight.finish(auto=auto):
            print("  " + line)
        print({
            "win": "\n전투에서 승리했다!\n",
            "lose": "\n파티가 전멸했다...\n",
            "fled": "\n무사히 도망쳤다.\n",
            "captured": "\n포획에 성공했다!\n",
        }.get(fight.result, ""))

    def ask_command(self, fight: Battle, ally: Monster) -> Action | None:
        hero = self.hero
        assert hero is not None
        while True:
            from tamer import passives as passive_rules

            index = prompt(
                f"\n{ally.name}의 행동은?"
                + (f"  [{', '.join(ally.passive_names())}]" if ally.passives else ""),
                [
                    "물리 공격 (상성 무시)",
                    f"스킬 공격 - {ally.species.skill_name} (SP {passive_rules.sp_cost(ally)})",
                    "방어",
                    "아이템",
                    "포획",
                    "도망",
                    "자동 전투",
                ],
                self.reader,
            )
            if index == 6:
                return None
            if index == 2:
                return Action(GUARD, ally)
            if index == 5:
                return Action(FLEE, ally)
            if index == 3:
                item = self.ask_item("소비")
                if item is None:
                    continue
                return Action(ITEM, ally, target=ally, item=item)
            if index == 4:
                ball = self.ask_item("볼")
                if ball is None:
                    continue
                target = self.ask_target(fight)
                if target is None:
                    continue
                return Action(CAPTURE, ally, target, item=ball)
            target = self.ask_target(fight)
            if target is None:
                continue
            return Action(ATTACK if index == 0 else SKILL, ally, target)

    def ask_target(self, fight: Battle) -> Monster | None:
        alive = fight.living(fight.enemies)
        if len(alive) == 1:
            return alive[0]
        index = prompt(
            "대상은?",
            [f"{enemy.name} (HP {enemy.hp}/{enemy.max_hp})" for enemy in alive] + ["취소"],
            self.reader,
        )
        return None if index == len(alive) else alive[index]

    def ask_item(self, category: str) -> str | None:
        hero = self.hero
        assert hero is not None
        usable = [
            name for name, count in hero.items.items()
            if count > 0 and self.data.items.get(name, {}).get("category") == category
        ]
        if not usable:
            print(f"쓸 수 있는 {category} 아이템이 없다.")
            return None
        index = prompt(
            "무엇을 쓸까?",
            [f"{name} x{hero.items[name]}" for name in usable] + ["취소"],
            self.reader,
        )
        return None if index == len(usable) else usable[index]


def demo(seed: int = 7) -> None:
    """비대화 데모: 고정 시드로 자동 전투 한 판을 돌린다."""
    data = load_game_data()
    rng = random.Random(seed)
    from tamer.models import Learned

    hero = Hero(name="카이", element="화", data=data, level=20)
    hero.items = {"포션": 3}
    hero.party = [
        Monster(data.by_name("폭염전갈"), data, level=20, passives=[Learned("strike", 2)]),
        Monster(data.by_name("화염늑대"), data, level=19, passives=[Learned("drain", 1)]),
    ]
    enemies = [
        Monster(data.by_name("고목수호자"), data, level=20, passives=[Learned("ironhide", 2)]),
        Monster(data.by_name("가시덤불"), data, level=18),
    ]
    print(RULE)
    print(f"{TITLE} — 자동 전투 데모")
    print(RULE)
    for monster in hero.party + enemies:
        print("  " + monster.status_line())
    print()

    fight = Battle(data=data, hero=hero, allies=hero.party, enemies=enemies, rng=rng)
    while not fight.finished:
        actions = [fight.auto_action(ally) for ally in fight.living(fight.allies)]
        for line in fight.run_round(actions):
            print("  " + line)
    for line in fight.finish(auto=True):
        print("  " + line)
    print(f"\n결과: {fight.result}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=f"{TITLE} — 텍스트 RPG")
    parser.add_argument("--demo", action="store_true", help="자동 전투 데모만 실행")
    parser.add_argument("--seed", type=int, default=None, help="난수 시드 고정")
    args = parser.parse_args(argv)

    if args.demo:
        demo(args.seed if args.seed is not None else 7)
        return 0

    rng = random.Random(args.seed)
    try:
        Game(load_game_data(), rng).run()
    except (Quit, KeyboardInterrupt):
        print("\n게임을 종료한다.")
    return 0

"""네트워크 기능 — 서버 없이 이 저장소 안에서 흉내 낸 오프라인 구현.

실제 통신은 하지 않는다. 상대 테이머 · 몬스터마트 매물 · 우체통 선물 · 친구의 섬은
전부 시드에서 결정적으로 생성한다. 나중에 진짜 서버를 붙이더라도 이 모듈의
함수 경계(상대 목록 가져오기 / 결과 정산하기)만 바꾸면 되도록 나눠 두었다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tamer.data import GRADE_ORDER, GameData
from tamer.models import Hero, Monster

TAMER_NAMES = [
    "하람", "노아", "제이", "린", "서우", "카이런", "미르", "타린", "유하", "벨",
    "이든", "소야", "라온", "테오", "나리", "쥰", "아린", "도윤", "세라", "훈",
]
TITLES = ["떠돌이", "수집가", "추격자", "은둔", "폭풍", "새벽", "그림자", "불꽃", "고요", "질주"]


@dataclass
class Rival:
    """대전 상대. 랭킹 포인트로 실력이 정해진다."""

    name: str
    rank_points: int
    party: list[Monster]

    def describe(self) -> str:
        team = ", ".join(f"{m.name} Lv{m.level}" for m in self.party)
        return f"{self.name} (RP {self.rank_points}) — {team}"


@dataclass
class BattleRecord:
    day: int
    mode: str
    opponent: str
    result: str
    rank_delta: int


@dataclass
class NetworkState:
    """저장 대상이 되는 네트워크 쪽 상태."""

    day: int = 1
    last_gift_day: int = 0
    last_market_day: int = 0
    last_chest_day: int = 0
    log: list[BattleRecord] = field(default_factory=list)


def _seeded(state: NetworkState, hero: Hero, salt: str) -> random.Random:
    """같은 날 같은 목적이면 같은 결과가 나오도록 시드를 고정한다."""
    return random.Random(f"{salt}:{state.day}:{hero.name}:{hero.rank_points}")


def _make_rival(data: GameData, rng: random.Random, hero: Hero, rank_points: int) -> Rival:
    level = max(1, hero.level + rng.randint(-3, 3))
    # 랭킹 포인트가 높을수록 상위 등급을 굴린다.
    tier = min(len(GRADE_ORDER) - 1, max(0, (rank_points - 800) // 250))
    size = 1 if hero.party_points < 4 else min(3, 1 + hero.party_points // 5)
    party = []
    for _ in range(size):
        grade = GRADE_ORDER[max(0, min(tier, rng.randint(max(0, tier - 1), tier)))]
        species = rng.choice(data.filter(grade=grade))
        party.append(Monster(species, data, level=max(1, level + rng.randint(-2, 2))))
    name = f"{rng.choice(TITLES)} {rng.choice(TAMER_NAMES)}"
    return Rival(name=name, rank_points=rank_points, party=party)


def find_rivals(data: GameData, state: NetworkState, hero: Hero, count: int = 5) -> list[Rival]:
    """내 랭킹 포인트 근처의 상대 목록. 배틀존의 랭킹배틀용."""
    rng = _seeded(state, hero, "rivals")
    spread = data.balance["network"]["rank_range"] * 10
    rivals = []
    for _ in range(count):
        points = max(100, hero.rank_points + rng.randint(-spread, spread))
        rivals.append(_make_rival(data, rng, hero, points))
    return rivals


def quick_rival(data: GameData, state: NetworkState, hero: Hero, rng: random.Random) -> Rival:
    """퀵배틀 — 범위 안에서 무작위로 상대가 정해진다."""
    spread = data.balance["network"]["rank_range"] * 10
    points = max(100, hero.rank_points + rng.randint(-spread, spread))
    return _make_rival(data, rng, hero, points)


def settle(
    data: GameData, state: NetworkState, hero: Hero, rival: Rival, mode: str, won: bool
) -> list[str]:
    """대전 결과를 랭킹 포인트 · 길드 랭킹 · 전적에 반영한다.

    친선배틀은 랭킹에 반영하지 않는다. 패배는 내가 진 경우에만 기록한다.
    랭킹이 걸린 대전에서 이기면 길드 랭킹이 한 칸 오르고, 일정 구간마다 테이머
    등급과 파티 포인트가 함께 오른다. 파티 포인트가 늘어야 상위 등급 몬스터를
    파티에 넣을 수 있으므로, 이 경로가 없으면 파티가 common에 갇힌다.
    """
    setting = data.balance["network"]
    delta = 0
    messages = []
    if mode != "친선배틀":
        delta = setting["rank_point_win"] if won else -setting["rank_point_loss"]
        hero.rank_points = max(0, hero.rank_points + delta)
        messages.append(f"랭킹 포인트 {delta:+d} (현재 {hero.rank_points})")
        if won and hero.guild_rank > 1:
            hero.guild_rank -= 1
            messages.append(f"길드 랭킹 {hero.guild_rank}위로 올라섰다.")
            messages += hero.promote()
    if won:
        hero.wins += 1
    else:
        hero.losses += 1
    state.log.append(
        BattleRecord(state.day, mode, rival.name, "승" if won else "패", delta)
    )
    del state.log[:-20]
    return messages


def leaderboard(data: GameData, state: NetworkState, hero: Hero, size: int = 10) -> list[tuple[str, int]]:
    """내 위아래로 늘어놓은 랭킹판. 내 자리는 이름 앞에 ▶ 가 붙는다."""
    rng = _seeded(state, hero, "board")
    rows = [(f"▶ {hero.name}", hero.rank_points)]
    for offset in range(1, size):
        rows.append((f"{rng.choice(TITLES)} {rng.choice(TAMER_NAMES)}",
                     max(50, hero.rank_points + rng.randint(-400, 400))))
    return sorted(rows, key=lambda row: -row[1])


# ------------------------------------------------------------------ 몬스터마트


@dataclass
class Listing:
    monster: Monster
    price: int
    seller: str


def market_price(data: GameData, monster: Monster) -> int:
    setting = data.balance["network"]
    multiplier = setting["market_grade_multiplier"][monster.species.grade]
    price = monster.level * setting["market_price_per_level"] * multiplier
    price *= 1.0 + monster.brain / 50
    if monster.evolved:
        price *= 1.5
    return max(50, int(price))


def market_listings(data: GameData, state: NetworkState, hero: Hero, count: int = 5) -> list[Listing]:
    """매물은 하루 단위로 바뀐다."""
    rng = _seeded(state, hero, "market")
    listings = []
    for _ in range(count):
        tier = min(len(GRADE_ORDER) - 1, max(0, rng.randint(0, 1 + hero.island_level // 12)))
        species = rng.choice(data.filter(grade=GRADE_ORDER[tier]))
        monster = Monster(species, data, level=max(1, hero.level + rng.randint(-4, 4)))
        monster.brain = rng.randint(0, 5)
        price = int(market_price(data, monster) * rng.uniform(0.9, 1.4))
        listings.append(Listing(monster, price, f"{rng.choice(TITLES)} {rng.choice(TAMER_NAMES)}"))
    return listings


def buy(hero: Hero, listing: Listing) -> list[str]:
    if hero.gold < listing.price:
        return [f"골드가 모자란다. ({listing.price} 필요)"]
    hero.gold -= listing.price
    return [f"{listing.monster.name}(을)를 {listing.price} 골드에 샀다.", hero.catch(listing.monster)]


def sell(hero: Hero, monster: Monster) -> list[str]:
    data = hero.data
    if monster in hero.party and len(hero.party) == 1:
        return ["마지막 파티 몬스터는 팔 수 없다."]
    price = int(market_price(data, monster) * data.balance["network"]["market_sell_ratio"])
    hero.gold += price
    if monster in hero.party:
        hero.party.remove(monster)
    elif monster in hero.storage:
        hero.storage.remove(monster)
    return [f"{monster.name}(을)를 {price} 골드에 팔았다."]


# ---------------------------------------------------------------------- 우체통


def collect_gifts(data: GameData, state: NetworkState, hero: Hero) -> list[str]:
    """하루에 한 번 친구들이 보낸 선물이 쌓인다."""
    if state.last_gift_day >= state.day:
        return ["오늘 받을 선물은 이미 다 받았다."]
    setting = data.balance["network"]
    rng = _seeded(state, hero, "gift")
    state.last_gift_day = state.day
    messages = []
    for _ in range(setting["mailbox_gifts_per_day"]):
        item = rng.choice(setting["mailbox_gift_pool"])
        hero.add_item(item)
        messages.append(f"{rng.choice(TAMER_NAMES)}(이)가 보낸 {item}(을)를 받았다.")
    return messages


def send_gift(hero: Hero, item: str) -> list[str]:
    """친구에게 아이템을 보낸다. 보낸 만큼 소지품에서 빠진다."""
    if not hero.take_item(item):
        return [f"{item}(이)가 없다."]
    return [f"{item}(을)를 친구에게 보냈다."]


# ------------------------------------------------------------------- 미지의 섬


def island_gain(data: GameData, hero: Hero, amount: int, *, visiting: bool) -> list[str]:
    """섬 경험치. 남의 섬에서 더 많이 벌고, 주인에게도 일부가 돌아간다."""
    setting = data.balance["island"]
    if visiting:
        amount = int(amount * setting["visit_experience_bonus"])
    hero.island_experience += amount
    messages = []
    need = setting["experience_per_level"] * hero.island_level
    while hero.island_level < setting["max_level"] and hero.island_experience >= need:
        hero.island_experience -= need
        hero.island_level += 1
        messages.append(f"미지의 섬 레벨이 {hero.island_level}이 되었다.")
        if hero.island_level in setting["party_point_levels"]:
            messages.append(f"파티 포인트가 늘었다. (현재 {hero.party_points})")
        need = setting["experience_per_level"] * hero.island_level
    return messages


def island_grade_cap(data: GameData, island_level: int) -> int:
    """섬 레벨에 따라 출현 상한 등급이 열린다."""
    unlock = data.balance["island"]["grade_unlock"]
    cap = GRADE_ORDER.index("rare")
    for grade, level in unlock.items():
        if island_level >= level:
            cap = max(cap, GRADE_ORDER.index(grade))
    return cap


def open_chest(data: GameData, state: NetworkState, hero: Hero) -> list[str]:
    """섬의 보물상자는 하루에 한 번 다시 찬다."""
    if state.last_chest_day >= state.day:
        return ["오늘 보물상자는 이미 열었다."]
    state.last_chest_day = state.day
    rng = _seeded(state, hero, "chest")
    messages = []
    gold = rng.randint(100, 300) * max(1, hero.island_level // 5)
    hero.gold += gold
    messages.append(f"보물상자에서 골드 {gold}(을)를 얻었다.")
    for _ in range(2):
        item = rng.choice(data.balance["network"]["mailbox_gift_pool"])
        hero.add_item(item)
        messages.append(f"보물상자에서 {item}(을)를 얻었다.")
    return messages


def friend_islands(data: GameData, state: NetworkState, hero: Hero, count: int = 3) -> list[tuple[str, int]]:
    """방문할 수 있는 친구의 섬 목록 (이름, 섬 레벨)."""
    rng = _seeded(state, hero, "islands")
    return [
        (f"{rng.choice(TITLES)} {rng.choice(TAMER_NAMES)}",
         max(1, hero.island_level + rng.randint(-5, 12)))
        for _ in range(count)
    ]

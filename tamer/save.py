"""저장 / 불러오기. 사람이 열어볼 수 있는 JSON 한 파일로 남긴다."""

from __future__ import annotations

import json
from pathlib import Path

from tamer.data import GameData
from tamer.models import Hero, Learned, Monster
from tamer.network import BattleRecord, NetworkState

SAVE_DIR = Path(__file__).resolve().parent.parent / "saves"
FORMAT_VERSION = 1


class SaveError(Exception):
    """저장 파일이 없거나 지금 도감과 맞지 않을 때."""


def save_path(name: str) -> Path:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_ ").strip() or "save"
    return SAVE_DIR / f"{safe}.json"


def list_saves() -> list[Path]:
    if not SAVE_DIR.exists():
        return []
    return sorted(SAVE_DIR.glob("*.json"))


def _monster_to_dict(monster: Monster) -> dict:
    return {
        "species": monster.species.name,
        "level": monster.level,
        "brain": monster.brain,
        "feel": monster.feel,
        "food": monster.food,
        "evolved": monster.evolved,
        "experience": monster.experience,
        "hp": monster.hp,
        "sp": monster.sp,
        "passives": [
            {"id": learned.passive_id, "level": learned.level} for learned in monster.passives
        ],
    }


def _monster_from_dict(data: GameData, payload: dict) -> Monster:
    monster = Monster(
        species=data.by_name(payload["species"]),
        data=data,
        level=payload["level"],
        brain=payload.get("brain", 0),
        feel=payload.get("feel", 0),
        food=payload.get("food", 100),
        evolved=payload.get("evolved", False),
        experience=payload.get("experience", 0),
        passives=[
            Learned(entry["id"], entry["level"]) for entry in payload.get("passives", [])
        ],
    )
    # HP/SP는 스탯 계산이 끝난 뒤에 덮어써야 최대치를 넘지 않는다.
    monster.hp = min(payload.get("hp", monster.max_hp), monster.max_hp)
    monster.sp = min(payload.get("sp", monster.max_sp), monster.max_sp)
    return monster


def to_dict(hero: Hero, state: NetworkState, area_index: int = 0) -> dict:
    return {
        "format": FORMAT_VERSION,
        "roster": hero.data.source,
        "area_index": area_index,
        "hero": {
            "name": hero.name,
            "element": hero.element,
            "level": hero.level,
            "experience": hero.experience,
            "stat_points": hero.stat_points,
            "rank_index": hero.rank_index,
            "gold": hero.gold,
            "guild_rank": hero.guild_rank,
            "rank_points": hero.rank_points,
            "wins": hero.wins,
            "losses": hero.losses,
            "island_level": hero.island_level,
            "island_experience": hero.island_experience,
            "items": dict(hero.items),
            "seen": sorted(hero.seen),
            "party": [_monster_to_dict(m) for m in hero.party],
            "storage": [_monster_to_dict(m) for m in hero.storage],
        },
        "network": {
            "day": state.day,
            "last_gift_day": state.last_gift_day,
            "last_market_day": state.last_market_day,
            "last_chest_day": state.last_chest_day,
            "log": [
                {
                    "day": record.day,
                    "mode": record.mode,
                    "opponent": record.opponent,
                    "result": record.result,
                    "rank_delta": record.rank_delta,
                }
                for record in state.log
            ],
        },
    }


def from_dict(data: GameData, payload: dict) -> tuple[Hero, NetworkState, int]:
    if payload.get("format") != FORMAT_VERSION:
        raise SaveError(f"저장 형식이 다르다. (파일 {payload.get('format')}, 지금 {FORMAT_VERSION})")
    body = payload["hero"]
    hero = Hero(
        name=body["name"],
        element=body["element"],
        data=data,
        level=body["level"],
        experience=body.get("experience", 0),
        stat_points=body.get("stat_points", 0),
        rank_index=body.get("rank_index", 0),
        gold=body.get("gold", 0),
        guild_rank=body.get("guild_rank", 99),
        rank_points=body.get("rank_points", 1000),
        wins=body.get("wins", 0),
        losses=body.get("losses", 0),
        island_level=body.get("island_level", 1),
        island_experience=body.get("island_experience", 0),
        items=dict(body.get("items", {})),
        seen=set(body.get("seen", [])),
    )
    try:
        hero.party = [_monster_from_dict(data, entry) for entry in body.get("party", [])]
        hero.storage = [_monster_from_dict(data, entry) for entry in body.get("storage", [])]
    except KeyError as error:
        raise SaveError(
            f"저장 파일의 몬스터 {error}(을)를 지금 도감에서 찾을 수 없다. "
            "저장할 때와 다른 도감을 쓰고 있지 않은지 확인한다."
        ) from error

    net = payload.get("network", {})
    state = NetworkState(
        day=net.get("day", 1),
        last_gift_day=net.get("last_gift_day", 0),
        last_market_day=net.get("last_market_day", 0),
        last_chest_day=net.get("last_chest_day", 0),
        log=[BattleRecord(**entry) for entry in net.get("log", [])],
    )
    return hero, state, payload.get("area_index", 0)


def write(hero: Hero, state: NetworkState, area_index: int = 0) -> Path:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = save_path(hero.name)
    path.write_text(
        json.dumps(to_dict(hero, state, area_index), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def read(data: GameData, path: Path) -> tuple[Hero, NetworkState, int]:
    if not path.exists():
        raise SaveError(f"{path} 가 없다.")
    return from_dict(data, json.loads(path.read_text(encoding="utf-8")))

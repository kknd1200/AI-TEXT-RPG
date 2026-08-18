#!/usr/bin/env python3
"""구형 안드로이드 게임 APK에서 데이터 테이블을 추출한다(선택 도구).

원본 에셋은 피처폰 시절 포맷 그대로다. 모든 문자열은 CP949이고,
바이너리 컨테이너는 아래 한 가지 형태만 쓴다.

    컨테이너: [u8 count][u32 offset × count][records...]
              offset 은 파일 선두 기준 절대값이다(중첩 컨테이너도 마찬가지).
    레코드:   [u8 len][name(CP949)] + 타입별 필드
    스탯목록: [u8 count][(u8 statIndex, u16 value) × count]

이 게임이 실제로 쓰는 도감은 tools/generate_roster.py 가 만드는 오리지널이다.
이 도구는 포맷 연구용이며, 뽑아낸 데이터는 원저작자의 저작물이므로 저장소에
넣지 않는다(.gitignore 로 data/extracted/ 를 막아 두었다). 각자 정당하게 가진
APK로 뽑아 TAMER_ROSTER=extracted 로 돌려보는 것까지만 상정한다.

사용법:
    python3 tools/extract_apk.py <APK 또는 assets 디렉터리> [-o data/extracted]
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

# item_stts.dat 의 스탯 인덱스 순서. 게임 내 도움말(method.fxt)의 몬스터 상태창
# 설명과 일치하며, 속성별 특화 스탯(화=STR, 광=MSTR, 풍=SPD, 목=CON)으로 검증했다.
STAT_KEYS = ["str", "dex", "mstr", "int", "con", "spd"]
GRADES = ["common", "uncommon", "rare", "special", "legend", "god"]
# item_stts.dat 에 등장하는 순서. 132종 = 6속성 × 22종.
ELEMENTS = ["수", "화", "목", "풍", "광", "악"]


class Assets:
    """APK(zip) 또는 이미 풀어놓은 디렉터리에서 assets/ 파일을 읽는다."""

    def __init__(self, source: Path):
        self.zip = None
        self.dir = None
        if source.is_dir():
            self.dir = source / "assets" if (source / "assets").is_dir() else source
        else:
            self.zip = zipfile.ZipFile(source)

    def read(self, name: str) -> bytes:
        if self.dir is not None:
            return (self.dir / name).read_bytes()
        return self.zip.read("assets/" + name)

    def names(self) -> list[str]:
        if self.dir is not None:
            return sorted(p.name for p in self.dir.iterdir() if p.is_file())
        return sorted(
            n[len("assets/"):] for n in self.zip.namelist() if n.startswith("assets/")
        )


def split_container(data: bytes, start: int = 0, end: int | None = None) -> list[tuple[int, int]]:
    """컨테이너를 레코드 (시작, 끝) 구간 목록으로 자른다.

    오프셋이 파일 절대값이므로 잘라낸 조각이 아니라 원본 버퍼 위에서 다뤄야
    중첩 컨테이너를 그대로 읽을 수 있다.
    """
    if end is None:
        end = len(data)
    count = data[start]
    bounds = list(struct.unpack_from("<%dI" % count, data, start + 1)) + [end]
    return [(bounds[i], bounds[i + 1]) for i in range(count)]


def read_str(buf: bytes, pos: int) -> tuple[str, int]:
    """[u8 len][CP949 bytes] 형태의 문자열을 읽고 다음 위치를 돌려준다."""
    length = buf[pos]
    return buf[pos + 1:pos + 1 + length].decode("cp949", "replace"), pos + 1 + length


def read_stats(buf: bytes, pos: int) -> dict[str, int]:
    """[u8 count][(u8 index, u16 value) × count] 스탯 목록을 읽는다."""
    count = buf[pos]
    stats = {}
    for i in range(count):
        idx = buf[pos + 1 + 3 * i]
        (value,) = struct.unpack_from("<H", buf, pos + 2 + 3 * i)
        stats[STAT_KEYS[idx]] = value
    return stats


def cp949_strings(blob: bytes, min_len: int = 2) -> list[str]:
    """바이너리에서 CP949 텍스트 조각만 훑어 뽑는다(포맷이 불명확한 파일용)."""
    out: list[str] = []
    cur = bytearray()
    i = 0
    while i < len(blob):
        b = blob[i]
        if 0x81 <= b <= 0xFD and i + 1 < len(blob) and 0x41 <= blob[i + 1] <= 0xFE:
            cur += blob[i:i + 2]
            i += 2
            continue
        if 0x20 <= b < 0x7F:
            cur.append(b)
            i += 1
            continue
        if len(cur) >= min_len:
            out.append(cur.decode("cp949", "replace"))
        cur = bytearray()
        i += 1
    if len(cur) >= min_len:
        out.append(cur.decode("cp949", "replace"))
    return out


def extract_monsters(assets: Assets) -> list[dict]:
    """item_mon.dat(이름+액티브스킬)과 item_stts.dat(속성/등급/기본스탯)을 합친다.

    두 파일은 레코드 수가 같고 인덱스가 1:1로 대응한다. 양쪽 레코드에 들어 있는
    등급 값이 서로 일치하는지 확인해서 그 대응을 검증한다.
    """
    mon_data = assets.read("item_mon.dat")
    stts_data = assets.read("item_stts.dat")
    mon_records = split_container(mon_data)
    stts_records = split_container(stts_data)
    if len(mon_records) != len(stts_records):
        raise SystemExit("item_mon.dat / item_stts.dat 레코드 수가 다르다")

    monsters = []
    for index, ((mb, _me), (sb, _se)) in enumerate(zip(mon_records, stts_records)):
        name, pos = read_str(mon_data, mb)
        pos += 1                                    # 레코드 타입(항상 0x01)
        (item_id,) = struct.unpack_from("<I", mon_data, pos)
        pos += 4
        skill_text, pos = read_str(mon_data, pos)
        grade = mon_data[pos]

        stts_name, spos = read_str(stts_data, sb)
        spos += 1                                   # 레코드 타입
        (stts_id,) = struct.unpack_from("<I", stts_data, spos)
        spos += 4
        spos += 1                                   # 예약
        stts_grade = stts_data[spos]
        spos += 1
        spos += 7                                   # 예약
        base = read_stats(stts_data, spos)

        if grade != stts_grade:
            raise SystemExit(f"[{index}] {name}: 등급 불일치 {grade} != {stts_grade}")

        # 액티브 스킬은 "이름/설명" 한 줄로 저장돼 있다.
        skill_name, _, skill_desc = skill_text.partition("/")
        element = stts_name.split("-")[0]

        monsters.append({
            "index": index,
            "item_id": item_id,
            "stts_id": stts_id,
            "name": name,
            "element": element,
            "grade": GRADES[grade],
            "grade_index": grade,
            "active_skill": {"name": skill_name, "description": skill_desc},
            "base_stats": base,
        })
    return monsters


def extract_element_growth(assets: Assets) -> dict[str, dict[str, dict[str, int]]]:
    """item_attr.dat: 속성 × 등급별 보정 스탯 테이블."""
    data = assets.read("item_attr.dat")
    table: dict[str, dict[str, dict[str, int]]] = {}
    for begin, end in split_container(data):
        name, pos = read_str(data, begin)
        if not name.startswith("속성스텟-"):
            continue
        element = name.split("-", 1)[1]
        table[element] = {}
        for sub_begin, sub_end in split_container(data, pos, end):
            grade_name, spos = read_str(data, sub_begin)
            spos += 8                               # 예약
            table[element][grade_name] = read_stats(data, spos)
    return table


def extract_passive_skills(assets: Assets) -> list[dict]:
    """item_skill.dat: 패시브 스킬. 같은 이름이 연속 여러 레코드(등급별)로 들어 있다."""
    data = assets.read("item_skill.dat")
    skills: list[dict] = []
    for begin, end in split_container(data):
        name, pos = read_str(data, begin)
        pos += 1                                    # 레코드 타입
        (item_id,) = struct.unpack_from("<I", data, pos)
        pos += 4
        description = ""
        # 설명이 붙은 레코드는 이름이 같은 묶음 중 첫 번째 하나뿐이다.
        if pos < end and 0 < data[pos] <= end - pos - 1:
            candidate, _ = read_str(data, pos)
            if re.search(r"[가-힣]", candidate):
                description = candidate
        if skills and skills[-1]["name"] == name:
            skills[-1]["variants"] += 1
            if description and not skills[-1]["description"]:
                skills[-1]["description"] = description
            continue
        skills.append({
            "item_id": item_id,
            "name": name,
            "description": description,
            "variants": 1,
        })
    return skills


def extract_items(assets: Assets) -> dict[str, list[str]]:
    """item_basic.dat: 카테고리별 아이템 이름 목록(중첩 컨테이너)."""
    data = assets.read("item_basic.dat")
    categories: dict[str, list[str]] = {}
    for begin, end in split_container(data):
        name, pos = read_str(data, begin)
        if set(name) <= {"-"} or end - pos < 2:
            continue
        names = []
        for sub_begin, _sub_end in split_container(data, pos, end):
            sub_name, _ = read_str(data, sub_begin)
            names.append(sub_name)
        categories[name] = names
    for simple in ("item_food.dat", "item_guild.dat"):
        blob = assets.read(simple)
        key = simple.replace("item_", "").replace(".dat", "")
        names = []
        for begin, _end in split_container(blob):
            sub_name, _ = read_str(blob, begin)
            if not set(sub_name) <= {"-"}:
                names.append(sub_name)
        categories[key] = names
    return categories


def extract_quests(assets: Assets) -> list[dict]:
    """qstlist.fxt: 3줄(제목 / 설명 / 목표)이 반복된다."""
    lines = [s.strip() for s in cp949_strings(assets.read("qstlist.fxt")) if s.strip()]
    lines = [s for s in lines if re.search(r"[가-힣]", s)]
    quests = []
    for i in range(0, len(lines) - 2, 3):
        quests.append({
            "id": len(quests),
            "title": lines[i],
            "description": lines[i + 1],
            "objective": lines[i + 2],
        })
    return quests


def extract_text(assets: Assets, filename: str) -> list[str]:
    return [
        s.strip()
        for s in cp949_strings(assets.read(filename))
        if s.strip() and re.search(r"[가-힣]", s)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="APK 파일 또는 압축을 푼 디렉터리")
    parser.add_argument("-o", "--out", type=Path, default=Path("data/extracted"))
    args = parser.parse_args()

    assets = Assets(args.source)
    args.out.mkdir(parents=True, exist_ok=True)

    monsters = extract_monsters(assets)
    payload = {
        "monsters.json": {
            "source": "item_mon.dat + item_stts.dat",
            "stat_order": STAT_KEYS,
            "monsters": monsters,
        },
        "element_growth.json": {
            "source": "item_attr.dat",
            "table": extract_element_growth(assets),
        },
        "passive_skills.json": {
            "source": "item_skill.dat",
            "skills": extract_passive_skills(assets),
        },
        "items.json": {
            "source": "item_basic.dat + item_food.dat + item_guild.dat",
            "categories": extract_items(assets),
        },
        "quests.json": {
            "source": "qstlist.fxt",
            "quests": extract_quests(assets),
        },
        "npcs.json": {
            "source": "npc.nm",
            "names": extract_text(assets, "npc.nm"),
        },
        "manual.json": {
            "source": "method.fxt + guild.fxt",
            "method": extract_text(assets, "method.fxt"),
            "guild": extract_text(assets, "guild.fxt"),
        },
        "messages.json": {
            "source": "msg.fxt",
            "lines": extract_text(assets, "msg.fxt"),
        },
    }

    for filename, content in payload.items():
        path = args.out / filename
        path.write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{path} 작성", file=sys.stderr)

    by_element: dict[str, int] = {}
    for monster in monsters:
        by_element[monster["element"]] = by_element.get(monster["element"], 0) + 1
    print(f"몬스터 {len(monsters)}종 " + " ".join(f"{k}:{v}" for k, v in by_element.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

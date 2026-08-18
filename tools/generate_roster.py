#!/usr/bin/env python3
"""이 프로젝트의 오리지널 몬스터 도감을 만든다.

이름 · 스킬 · 스탯 곡선 전부 이 저장소에서 새로 지은 것이고, 특정 상용 게임의
데이터를 옮겨 담지 않는다. 시스템 구조(6속성 × 22종, 6등급)는 장르 관습이다.

    python3 tools/generate_roster.py -o data/roster.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

GRADES = ["common", "uncommon", "rare", "special", "legend", "god"]
# 속성별 등급 구성. 아래로 갈수록 귀해진다.
GRADE_SHAPE = [("common", 4), ("uncommon", 5), ("rare", 4), ("special", 4), ("legend", 3), ("god", 2)]
STAT_KEYS = ["str", "dex", "mstr", "int", "con", "spd"]

# 속성 6종과 그 성격. 상성 순환은 화>목>풍>수>화, 광과 악은 서로 물고 물린다.
# 가중치 합은 속성마다 6.05로 같게 맞춰, 속성 선택 자체가 유불리가 되지 않게 했다.
ELEMENTS = {
    "수": {"archetype": "밸런스형", "weights": [1.00, 1.05, 1.05, 1.00, 1.00, 0.95]},
    "화": {"archetype": "물리 공격형", "weights": [1.35, 1.00, 0.90, 0.85, 1.00, 0.95]},
    "목": {"archetype": "체력형", "weights": [1.00, 1.10, 0.90, 0.95, 1.35, 0.80]},
    "풍": {"archetype": "속도형", "weights": [1.05, 0.90, 0.95, 0.85, 0.90, 1.40]},
    "광": {"archetype": "스킬 공격형", "weights": [0.85, 0.95, 1.35, 1.10, 0.90, 0.90]},
    "악": {"archetype": "복합형", "weights": [1.15, 0.90, 1.10, 1.15, 0.90, 0.85]},
}

# 등급별 레벨 1 기준치와 레벨당 성장치(10배 정수로 저장한다).
GRADE_TIER = {
    "common": (10, 12), "uncommon": (16, 16), "rare": (24, 21),
    "special": (34, 26), "legend": (46, 31), "god": (60, 36),
}

NAMES = {
    "수": [
        "아쿠아링", "물꽃게", "이슬누리", "개구리왕눈",
        "파도치", "산호돌이", "해무늘보", "물갈퀴범", "조개장군",
        "심해아귀", "빙정사슴", "해류뱀", "물기둥거신",
        "창천고래", "서리마녀", "소용돌이수호자", "해령무사",
        "만조의룡", "심연사제", "해왕상어",
        "대해군주", "창해신",
    ],
    "화": [
        "불씨쥐", "잉걸새", "화롯이", "재두더지",
        "화염늑대", "용암달팽이", "숯불곰", "불꽃무희", "연기여우",
        "폭염전갈", "마그마골렘", "화산도마뱀", "불새정령",
        "작열기사", "화룡새끼", "열풍술사", "잿빛거인",
        "겁화의룡", "태양수호자", "용암군주",
        "대화염제", "염룡신",
    ],
    "목": [
        "새싹몬", "도토리쥐", "넝쿨이", "이끼두꺼비",
        "가시덤불", "버섯광대", "느림보정령", "꽃사슴", "씨앗술사",
        "고목수호자", "독초거미", "대나무무사", "뿌리거인",
        "세계수묘목", "숲의마녀", "가시장미기사", "수액드래곤",
        "천년고목", "대지의사제", "숲왕사자",
        "세계수화신", "녹룡신",
    ],
    "풍": [
        "산들새", "민들레씨", "회오리쥐", "깃털토끼",
        "질풍표범", "구름양", "바람가오리", "소리매", "회전날다람쥐",
        "폭풍독수리", "진공사마귀", "하늘연무사", "번개제비",
        "태풍기사", "창공비룡", "무풍술사", "하늘고래",
        "폭풍의룡", "창천수호자", "질풍군주",
        "대풍신", "천공제",
    ],
    "광": [
        "반딧불이", "빛구슬", "햇살나비", "별똥쥐",
        "성광기사", "은빛여우", "서광새", "광휘사슴", "빛의무희",
        "백광사자", "성혼술사", "광검전사", "여명천사",
        "대천사병", "광휘룡", "성좌술사", "백야기사",
        "여명의룡", "대성당수호자", "광명사제",
        "광휘신", "태양신관",
    ],
    "악": [
        "그림자쥐", "검은박쥐", "저주인형", "늪귀신",
        "밤까마귀", "해골병사", "흑묘요괴", "독무령", "그믐늑대",
        "사령술사", "흑염거미", "망령기사", "어둠거인",
        "흑룡새끼", "심연마녀", "저주공작", "암흑기사",
        "심연의룡", "나락사제", "흑월군주",
        "암흑제", "나락신",
    ],
}

# 속성마다 액티브 스킬 8종. 앞쪽이 저등급, 뒤쪽이 고등급용이다.
SKILLS = {
    "수": [
        ("물대포", "물줄기를 쏘아 맞힌다"), ("거품폭풍", "거품으로 시야를 덮는다"),
        ("소용돌이", "적을 휘감아 끌어당긴다"), ("한파", "얼려서 움직임을 늦춘다"),
        ("빙결창", "얼음 창으로 꿰뚫는다"), ("심해압", "수압으로 짓누른다"),
        ("해일", "거센 물결로 쓸어버린다"), ("대해일", "바다를 통째로 들이붓는다"),
    ],
    "화": [
        ("불꽃탄", "작은 불덩이를 던진다"), ("연기폭발", "연기와 함께 터뜨린다"),
        ("화염방사", "불길을 내뿜는다"), ("작열베기", "달군 발톱으로 벤다"),
        ("용암분출", "발밑에서 용암을 뿜는다"), ("화산탄", "불덩이를 쏟아붓는다"),
        ("겁화", "꺼지지 않는 불로 태운다"), ("천화멸", "하늘에서 불비를 내린다"),
    ],
    "목": [
        ("덩굴채찍", "덩굴을 휘둘러 때린다"), ("씨앗포", "단단한 씨앗을 쏜다"),
        ("뿌리결박", "뿌리로 발을 묶는다"), ("잎날폭풍", "잎사귀 칼날을 날린다"),
        ("가시갑주", "가시를 세워 반격한다"), ("대지진동", "땅을 흔들어 넘어뜨린다"),
        ("숲의분노", "숲 전체가 달려든다"), ("세계수숨결", "세계수의 기운을 쏟는다"),
    ],
    "풍": [
        ("돌풍", "거센 바람으로 밀친다"), ("깃털칼날", "깃털을 칼처럼 날린다"),
        ("회오리", "작은 회오리에 가둔다"), ("진공날", "공기를 갈라 벤다"),
        ("질풍연격", "눈에 안 보이게 연타한다"), ("폭풍우", "비바람으로 몰아친다"),
        ("창공가르기", "하늘째로 갈라놓는다"), ("대선풍", "모든 것을 날려버린다"),
    ],
    "광": [
        ("섬광", "눈부신 빛을 터뜨린다"), ("성광탄", "빛 구슬을 쏜다"),
        ("정화의빛", "어둠을 걷어낸다"), ("광선검", "빛으로 벼린 검을 휘두른다"),
        ("여명의창", "새벽빛 창을 던진다"), ("성역", "빛의 결계로 짓누른다"),
        ("심판의빛", "하늘에서 빛기둥이 떨어진다"), ("천상광휘", "온 하늘이 빛난다"),
    ],
    "악": [
        ("그림자손톱", "그림자를 세워 할퀸다"), ("저주", "약한 저주를 건다"),
        ("흡혈", "상대의 기운을 빨아들인다"), ("암흑탄", "어둠 덩어리를 쏜다"),
        ("공포의포효", "겁을 주어 위축시킨다"), ("사념의칼날", "원념을 칼로 벼린다"),
        ("나락의손길", "발밑에서 손이 솟는다"), ("종말의어둠", "빛을 통째로 삼킨다"),
    ],
}

# 등급별로 쓸 수 있는 스킬 구간.
SKILL_BAND = {
    "common": (0, 1), "uncommon": (1, 2), "rare": (2, 3),
    "special": (4, 5), "legend": (5, 6), "god": (6, 7),
}


def jitter(name: str, stat: str) -> float:
    """이름에서 결정적으로 뽑는 ±8% 편차. 같은 등급이라도 개체차가 생긴다."""
    digest = hashlib.sha256(f"{name}:{stat}".encode()).digest()
    return 0.92 + (digest[0] / 255) * 0.16


def build() -> dict:
    monsters = []
    index = 0
    for element, profile in ELEMENTS.items():
        names = NAMES[element]
        if len(names) != sum(count for _, count in GRADE_SHAPE):
            raise SystemExit(f"{element}: 이름 개수가 등급 구성과 맞지 않는다")
        cursor = 0
        for grade, count in GRADE_SHAPE:
            base_tier, growth_tier = GRADE_TIER[grade]
            low, high = SKILL_BAND[grade]
            for slot in range(count):
                name = names[cursor]
                cursor += 1
                skill_name, skill_desc = SKILLS[element][low + slot % (high - low + 1)]
                base_stats, growth = {}, {}
                for position, key in enumerate(STAT_KEYS):
                    weight = profile["weights"][position]
                    spread = jitter(name, key)
                    base_stats[key] = max(1, round(base_tier * weight * spread))
                    growth[key] = max(1, round(growth_tier * weight * spread))
                monsters.append({
                    "index": index,
                    "name": name,
                    "element": element,
                    "grade": grade,
                    "active_skill": {"name": skill_name, "description": skill_desc},
                    "base_stats": base_stats,
                    "growth": growth,
                })
                index += 1
    return {
        "origin": "이 저장소에서 만든 오리지널 도감",
        "stat_order": STAT_KEYS,
        "elements": {name: profile["archetype"] for name, profile in ELEMENTS.items()},
        "monsters": monsters,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=Path("data/roster.json"))
    args = parser.parse_args()
    payload = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{args.out}: 몬스터 {len(payload['monsters'])}종")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

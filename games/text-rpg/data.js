/* ==========================================================================
   잊혀진 탑 — 게임 데이터
   직업 · 몬스터 · 아이템 · 이벤트 정의
   ========================================================================== */

window.GAME_DATA = (function () {
  'use strict';

  /* --- 직업 -------------------------------------------------------------- */

  var CLASSES = [
    {
      id: 'warrior',
      name: '전사',
      emoji: '⚔️',
      blurb: '두꺼운 갑주와 흔들리지 않는 검. 맞으면서 이기는 직업입니다.',
      base: { hp: 64, mp: 16, atk: 11, def: 8, spd: 5, luk: 3 },
      growth: { hp: 9, mp: 2.4, atk: 2.2, def: 1.8, spd: .5, luk: .4 },
      skill: {
        name: '분쇄격', cost: 6, mult: 1.85, type: 'phys',
        desc: '무기를 내리찍어 큰 물리 피해를 줍니다.',
        text: '{name}이(가) 온몸을 실어 무기를 내리찍었다!'
      },
      startItems: ['potion_s', 'potion_s', 'whetstone']
    },
    {
      id: 'rogue',
      name: '도적',
      emoji: '🗡️',
      blurb: '빠른 발과 정확한 급소. 먼저 때리고 크게 터뜨립니다.',
      base: { hp: 54, mp: 22, atk: 10, def: 5, spd: 11, luk: 9 },
      growth: { hp: 7.4, mp: 3.2, atk: 2.1, def: 1.35, spd: 1.3, luk: 1.2 },
      skill: {
        name: '급소 찌르기', cost: 6, mult: 1.5, type: 'phys', critBonus: .45,
        desc: '치명타 확률이 크게 오르는 일격을 찌릅니다.',
        text: '{name}이(가) 그림자처럼 파고들어 급소를 노렸다!'
      },
      startItems: ['potion_s', 'potion_s', 'lucky_coin']
    },
    {
      id: 'mage',
      name: '마법사',
      emoji: '🔮',
      blurb: '얇은 몸, 무거운 주문. 방어를 무시하는 화력으로 찍어 누릅니다.',
      base: { hp: 48, mp: 34, atk: 9, def: 4, spd: 6, luk: 5 },
      growth: { hp: 6.6, mp: 5.5, atk: 2.0, def: 1.2, spd: .7, luk: .8 },
      skill: {
        name: '화염구', cost: 7, mult: 2.2, type: 'magic',
        desc: '상대의 방어를 절반만 계산하는 불덩이를 던집니다.',
        text: '{name}의 손끝에서 불덩이가 부풀어 올랐다!'
      },
      startItems: ['potion_s', 'ether_s', 'ether_s']
    }
  ];

  /* --- 아이템 ------------------------------------------------------------ */

  var ITEMS = {
    potion_s:  { id: 'potion_s',  name: '작은 회복약', emoji: '🧪', type: 'heal',  value: 35, price: 24, desc: 'HP를 35 회복합니다.' },
    potion_l:  { id: 'potion_l',  name: '큰 회복약',   emoji: '🍷', type: 'heal',  value: 90, price: 62, desc: 'HP를 90 회복합니다.' },
    ether_s:   { id: 'ether_s',   name: '마력 물약',   emoji: '💧', type: 'mana',  value: 20, price: 30, desc: 'MP를 20 회복합니다.' },
    elixir:    { id: 'elixir',    name: '엘릭서',      emoji: '✨', type: 'full',  value: 0,  price: 160, desc: 'HP와 MP를 모두 회복합니다.' },
    bomb:      { id: 'bomb',      name: '섬광 폭탄',   emoji: '💣', type: 'damage', value: 45, price: 48, desc: '적에게 45의 고정 피해를 줍니다.' },
    whetstone: { id: 'whetstone', name: '숫돌',        emoji: '🪨', type: 'buff',  stat: 'atk', value: 2, price: 70, desc: '공격력이 영구히 2 오릅니다.' },
    tonic:     { id: 'tonic',     name: '강장제',      emoji: '🥤', type: 'buff',  stat: 'maxHp', value: 12, price: 80, desc: '최대 HP가 영구히 12 오릅니다.' },
    lucky_coin:{ id: 'lucky_coin',name: '행운의 동전', emoji: '🪙', type: 'buff',  stat: 'luk', value: 3, price: 75, desc: '행운이 영구히 3 오릅니다.' },
    smoke:     { id: 'smoke',     name: '연막탄',      emoji: '🌫️', type: 'escape', value: 0, price: 35, desc: '전투에서 반드시 도망칩니다. (층주 제외)' }
  };

  // 상점에 진열되는 물건들
  var SHOP_STOCK = ['potion_s', 'potion_l', 'ether_s', 'bomb', 'smoke', 'whetstone', 'tonic', 'lucky_coin', 'elixir'];

  /* --- 몬스터 ------------------------------------------------------------ */

  // tier: 등장하기 시작하는 최소 층
  var MONSTERS = [
    { id: 'rat',      name: '탑쥐',          emoji: '🐀', tier: 1, hp: 26,  atk: 7,  def: 2,  spd: 7,  exp: 10, gold: 9,
      flavor: '먼지 속에서 붉은 눈 한 쌍이 반짝인다.' },
    { id: 'bat',      name: '동굴 박쥐',      emoji: '🦇', tier: 1, hp: 22,  atk: 8,  def: 1,  spd: 12, exp: 11, gold: 10,
      flavor: '천장에서 날개 소리가 쏟아져 내린다.' },
    { id: 'slime',    name: '점액 덩어리',    emoji: '🟢', tier: 1, hp: 34,  atk: 6,  def: 5,  spd: 3,  exp: 12, gold: 11,
      flavor: '계단 한 칸을 통째로 덮은 점액이 꿈틀거린다.' },
    { id: 'goblin',   name: '고블린 척후병',  emoji: '👺', tier: 3, hp: 40,  atk: 11, def: 4,  spd: 8,  exp: 18, gold: 17,
      flavor: '녹슨 단검을 든 고블린이 이를 드러낸다.' },
    { id: 'skeleton', name: '해골 병사',      emoji: '💀', tier: 4, hp: 46,  atk: 13, def: 7,  spd: 6,  exp: 22, gold: 20,
      flavor: '무너진 갑옷이 스스로 일어나 검을 든다.' },
    { id: 'wolf',     name: '잿빛 늑대',      emoji: '🐺', tier: 5, hp: 52,  atk: 15, def: 5,  spd: 13, exp: 26, gold: 22,
      flavor: '낮은 으르렁 소리가 벽을 타고 번진다.' },
    { id: 'wraith',   name: '탑의 원령',      emoji: '👻', tier: 7, hp: 58,  atk: 18, def: 6,  spd: 10, exp: 34, gold: 30,
      flavor: '차가운 손이 등 뒤에서 어깨를 짚는다.' },
    { id: 'golem',    name: '석상 수호자',    emoji: '🗿', tier: 9, hp: 90,  atk: 19, def: 15, spd: 3,  exp: 46, gold: 42,
      flavor: '석상이 눈을 뜨고 통로를 가로막는다.' },
    { id: 'knight',   name: '타락한 기사',    emoji: '🛡️', tier: 11, hp: 96, atk: 24, def: 13, spd: 8,  exp: 58, gold: 55,
      flavor: '투구 틈으로 검은 연기가 새어 나온다.' },
    { id: 'chimera',  name: '키메라',        emoji: '🦁', tier: 14, hp: 120, atk: 29, def: 12, spd: 12, exp: 76, gold: 70,
      flavor: '세 개의 머리가 동시에 당신을 노려본다.' }
  ];

  var BOSSES = [
    { id: 'boss_gate',   name: '문지기 오르그', emoji: '👹', hp: 95,  atk: 16, def: 9,  spd: 6,  exp: 70,  gold: 90,
      flavor: '거대한 그림자가 계단을 통째로 막고 서 있다.' },
    { id: 'boss_witch',  name: '재의 마녀',     emoji: '🧙', hp: 150, atk: 24, def: 11, spd: 11, exp: 130, gold: 160,
      flavor: '잿가루가 소용돌이치며 사람의 형상을 이룬다.' },
    { id: 'boss_dragon', name: '어린 흑룡',     emoji: '🐉', hp: 230, atk: 33, def: 16, spd: 9,  exp: 220, gold: 280,
      flavor: '뜨거운 숨결이 돌계단을 붉게 달군다.' },
    { id: 'boss_lord',   name: '탑의 주인',     emoji: '👑', hp: 340, atk: 42, def: 20, spd: 13, exp: 360, gold: 450,
      flavor: '왕좌에 앉은 무언가가 천천히 고개를 들었다.' }
  ];

  /* --- 탐험 이벤트 -------------------------------------------------------- */

  var EVENTS = [
    {
      id: 'shrine',
      title: '금이 간 제단',
      text: '벽감 속 제단이 희미하게 빛난다. 손을 얹으면 무언가 일어날 것 같다.',
      choices: [
        { label: '손을 얹는다', outcome: 'shrine_touch' },
        { label: '그냥 지나친다', outcome: 'pass' }
      ]
    },
    {
      id: 'chest',
      title: '먼지 쌓인 상자',
      text: '벽 구석에 상자가 놓여 있다. 자물쇠는 이미 부서져 있다.',
      choices: [
        { label: '열어 본다', outcome: 'chest_open' },
        { label: '함정 같다, 지나친다', outcome: 'pass' }
      ]
    },
    {
      id: 'fountain',
      title: '맑은 샘',
      text: '벽 틈에서 흘러나온 물이 작은 웅덩이를 이루고 있다.',
      choices: [
        { label: '물을 마신다', outcome: 'fountain_drink' },
        { label: '수통만 채우고 간다', outcome: 'pass' }
      ]
    },
    {
      id: 'corpse',
      title: '먼저 온 도전자',
      text: '벽에 기댄 채 굳어 버린 모험가. 배낭이 아직 그대로다.',
      choices: [
        { label: '배낭을 뒤진다', outcome: 'corpse_loot' },
        { label: '예를 갖추고 지나간다', outcome: 'corpse_pray' }
      ]
    },
    {
      id: 'gambler',
      title: '수상한 도박꾼',
      text: '"동전 한 번에 판돈 두 배. 어때, 올라가는 길에 심심하잖아?"',
      choices: [
        { label: '건다 (골드 40)', outcome: 'gamble', cost: 40 },
        { label: '사양한다', outcome: 'pass' }
      ]
    }
  ];

  return {
    CLASSES: CLASSES,
    ITEMS: ITEMS,
    SHOP_STOCK: SHOP_STOCK,
    MONSTERS: MONSTERS,
    BOSSES: BOSSES,
    EVENTS: EVENTS
  };
}());

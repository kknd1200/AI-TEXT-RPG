/*
 * 게임 레지스트리
 * ------------------------------------------------------------------
 * 새 웹게임을 추가하려면:
 *   1) games/<게임아이디>/ 폴더를 만들고 index.html 을 넣습니다.
 *   2) 아래 배열에 항목을 하나 추가합니다.
 *
 * 필드 설명
 *   id       : 고유 아이디 (URL에 쓰임, 영문/숫자/하이픈)
 *   title    : 게임 이름
 *   tagline  : 카드에 보이는 한 줄 소개
 *   desc     : 상세 설명
 *   path     : 실행할 경로. 저장소 내부 게임은 "games/<id>/index.html",
 *              외부에 배포된 게임이면 "https://..." 전체 URL
 *   external : true 면 iframe 대신 새 탭으로 엽니다 (선택)
 *   tags     : 필터/검색에 쓰이는 태그 배열
 *   emoji    : 카드 커버에 표시할 이모지
 *   accent   : 카드 커버 그라디언트 색 [시작, 끝]
 *   status   : "playable" | "wip" | "soon"
 *   players  : 인원 표기 (선택)
 *   updated  : 최근 업데이트 (YYYY-MM-DD)
 * ------------------------------------------------------------------
 */
window.GAME_REGISTRY = [
  {
    id: 'text-rpg',
    title: '잊혀진 탑',
    tagline: '선택으로 쌓아 올리는 텍스트 로그라이트 RPG',
    desc:
      '세 가지 직업 중 하나를 골라 끝없이 이어지는 탑을 오릅니다. ' +
      '전투·보물·야영·상인 이벤트가 무작위로 등장하며, 5층마다 층주가 길을 막습니다. ' +
      '진행 상황은 브라우저에 자동 저장됩니다.',
    path: 'games/text-rpg/index.html',
    tags: ['RPG', '텍스트', '싱글플레이', '로그라이트'],
    emoji: '🗼',
    accent: ['#7c5cff', '#22d3ee'],
    status: 'playable',
    players: '1인',
    updated: '2026-09-02'
  }
];

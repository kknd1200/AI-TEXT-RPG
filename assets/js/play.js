/* ==========================================================================
   ARCADE — 게임 플레이어
   play.html?game=<id> 로 들어온 게임을 iframe 안에서 실행합니다.
   ========================================================================== */

(function () {
  'use strict';

  var THEME_KEY = 'arcade:theme';

  // 홈페이지에서 고른 테마를 그대로 유지합니다.
  try {
    var saved = localStorage.getItem(THEME_KEY);
    if (saved) { document.documentElement.setAttribute('data-theme', saved); }
  } catch (e) { /* 저장소 접근 불가 시 기본 테마 사용 */ }

  var games = Array.isArray(window.GAME_REGISTRY) ? window.GAME_REGISTRY : [];
  var id = new URLSearchParams(window.location.search).get('game');

  var game = null;
  for (var i = 0; i < games.length; i++) {
    if (games[i].id === id) { game = games[i]; break; }
  }

  var shell = document.getElementById('shell');
  var errorBox = document.getElementById('playError');

  function fail(message) {
    shell.hidden = true;
    errorBox.hidden = false;
    if (message) { document.getElementById('errorDetail').textContent = message; }
  }

  if (!id) {
    fail('주소에 실행할 게임이 지정되지 않았습니다. 목록에서 게임을 선택해 주세요.');
    return;
  }
  if (!game) {
    fail('"' + id + '" 게임을 목록에서 찾을 수 없습니다. games/games.js 에 등록되어 있는지 확인해 주세요.');
    return;
  }
  if (game.status === 'soon') {
    fail('"' + game.title + '"은(는) 아직 준비 중입니다.');
    return;
  }

  document.title = game.title + ' — ARCADE';
  document.getElementById('playTitle').textContent = game.title;
  document.getElementById('playTagline').textContent = game.tagline || '';
  document.getElementById('playEmoji').textContent = game.emoji || '🎮';

  var frame = document.getElementById('gameFrame');
  frame.src = game.path;
  frame.title = game.title + ' 게임 화면';

  var newTab = document.getElementById('newTabBtn');
  newTab.href = game.path;

  document.getElementById('reloadBtn').addEventListener('click', function () {
    // src 를 다시 지정해 게임을 처음부터 시작합니다.
    frame.src = 'about:blank';
    window.setTimeout(function () { frame.src = game.path; }, 0);
  });

  document.getElementById('fullscreenBtn').addEventListener('click', function () {
    var stage = document.getElementById('stage');
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else if (stage.requestFullscreen) {
      stage.requestFullscreen();
    } else if (stage.webkitRequestFullscreen) {
      stage.webkitRequestFullscreen();
    }
  });
}());

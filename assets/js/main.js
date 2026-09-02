/* ==========================================================================
   ARCADE — 홈페이지 스크립트
   games/games.js 의 GAME_REGISTRY 를 읽어 카드 목록을 그리고,
   검색 · 태그 필터 · 테마 전환을 담당합니다.
   ========================================================================== */

(function () {
  'use strict';

  var THEME_KEY = 'arcade:theme';
  var games = Array.isArray(window.GAME_REGISTRY) ? window.GAME_REGISTRY : [];

  var grid        = document.getElementById('gameGrid');
  var tagBox      = document.getElementById('tagFilters');
  var searchInput = document.getElementById('searchInput');
  var emptyState  = document.getElementById('emptyState');

  var activeTag = null;
  var query = '';

  /* --- 테마 -------------------------------------------------------------- */

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* 저장 불가 시 무시 */ }
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch (e) { /* 무시 */ }
    if (!saved) {
      saved = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
        ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', saved);

    var toggle = document.getElementById('themeToggle');
    if (toggle) {
      toggle.addEventListener('click', function () {
        var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(next);
      });
    }
  }

  /* --- 유틸 -------------------------------------------------------------- */

  var STATUS = {
    playable: { label: 'PLAY', cls: 'is-playable' },
    wip:      { label: '개발 중', cls: 'is-wip' },
    soon:     { label: '준비 중', cls: 'is-soon' }
  };

  function isExternal(game) {
    return game.external === true || /^https?:\/\//i.test(game.path || '');
  }

  function playUrl(game) {
    return isExternal(game) && game.external
      ? game.path
      : 'play.html?game=' + encodeURIComponent(game.id);
  }

  function haystack(game) {
    return [game.title, game.tagline, game.desc]
      .concat(game.tags || [])
      .join(' ')
      .toLowerCase();
  }

  /* --- 카드 렌더링 -------------------------------------------------------- */

  function buildCard(game) {
    var accent = game.accent || ['#5b3df5', '#22d3ee'];
    var status = STATUS[game.status] || STATUS.playable;
    var playable = game.status !== 'soon';

    var card = document.createElement(playable ? 'a' : 'div');
    card.className = 'game-card';
    if (playable) {
      card.href = playUrl(game);
      if (game.external) { card.target = '_blank'; card.rel = 'noopener'; }
    }

    var cover = document.createElement('div');
    cover.className = 'card-cover';
    cover.style.setProperty('--c1', accent[0]);
    cover.style.setProperty('--c2', accent[1] || accent[0]);

    var badge = document.createElement('span');
    badge.className = 'card-badge ' + status.cls;
    badge.textContent = status.label;

    var emoji = document.createElement('span');
    emoji.className = 'card-emoji';
    emoji.setAttribute('aria-hidden', 'true');
    emoji.textContent = game.emoji || '🎮';

    cover.append(badge, emoji);

    var body = document.createElement('div');
    body.className = 'card-body';

    var title = document.createElement('h3');
    title.textContent = game.title;

    var tagline = document.createElement('p');
    tagline.className = 'card-tagline';
    tagline.textContent = game.tagline || game.desc || '';

    body.append(title, tagline);

    if (game.tags && game.tags.length) {
      var tags = document.createElement('div');
      tags.className = 'card-tags';
      game.tags.forEach(function (t) {
        var el = document.createElement('span');
        el.textContent = t;
        tags.appendChild(el);
      });
      body.appendChild(tags);
    }

    var foot = document.createElement('div');
    foot.className = 'card-foot';

    var meta = document.createElement('span');
    meta.textContent = [game.players, game.updated].filter(Boolean).join(' · ');

    var action = document.createElement('span');
    action.className = 'card-play';
    action.textContent = playable ? (game.external ? '새 탭에서 열기 ↗' : '플레이 →') : '준비 중';

    foot.append(meta, action);
    body.appendChild(foot);

    card.append(cover, body);
    return card;
  }

  function render() {
    var q = query.trim().toLowerCase();
    var visible = games.filter(function (game) {
      var tagOk = !activeTag || (game.tags || []).indexOf(activeTag) !== -1;
      var textOk = !q || haystack(game).indexOf(q) !== -1;
      return tagOk && textOk;
    });

    grid.textContent = '';
    visible.forEach(function (game) { grid.appendChild(buildCard(game)); });

    emptyState.hidden = visible.length > 0;
  }

  /* --- 태그 필터 ---------------------------------------------------------- */

  function renderTags() {
    var all = [];
    games.forEach(function (game) {
      (game.tags || []).forEach(function (t) {
        if (all.indexOf(t) === -1) { all.push(t); }
      });
    });
    if (!all.length) { return; }

    all.sort(function (a, b) { return a.localeCompare(b, 'ko'); });
    all.unshift(null); // "전체"

    all.forEach(function (tag) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'tag-chip';
      chip.textContent = tag === null ? '전체' : tag;
      chip.setAttribute('aria-pressed', String(tag === activeTag));
      chip.addEventListener('click', function () {
        activeTag = (activeTag === tag) ? null : tag;
        Array.prototype.forEach.call(tagBox.children, function (c) {
          c.setAttribute('aria-pressed', String(c.dataset.tag === (activeTag === null ? '' : activeTag)));
        });
        render();
      });
      chip.dataset.tag = tag === null ? '' : tag;
      tagBox.appendChild(chip);
    });
  }

  /* --- 시작 -------------------------------------------------------------- */

  initTheme();

  var yearEl = document.getElementById('year');
  if (yearEl) { yearEl.textContent = new Date().getFullYear(); }

  var countEl = document.getElementById('statCount');
  if (countEl) { countEl.textContent = games.length + '개'; }

  if (!grid) { return; }

  if (!games.length) {
    emptyState.textContent = '아직 등록된 게임이 없습니다. games/games.js 에 게임을 추가해 보세요.';
    emptyState.hidden = false;
    return;
  }

  renderTags();
  render();

  if (searchInput) {
    searchInput.addEventListener('input', function (e) {
      query = e.target.value;
      render();
    });
  }
}());

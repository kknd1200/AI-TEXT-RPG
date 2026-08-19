/* 화면. 세로 한 칸, 상단 상태바 · 가운데 스크롤 · 하단 커맨드 독으로 고정한다. */

(function () {
  "use strict";
  const G = window.Game;

  const app = document.getElementById("app");
  const toastBox = document.getElementById("toast");

  let hero = null;
  let stack = [];          // 화면 스택. 뒤로 가기용
  let fight = null;        // 진행 중인 전투
  let pending = [];        // 이번 라운드에 모은 아군 커맨드
  let toastTimer = null;

  /* ── DOM 도우미 ─────────────────────────────────────────── */

  function el(tag, props, kids) {
    const node = document.createElement(tag);
    if (props) {
      for (const [key, value] of Object.entries(props)) {
        if (key === "class") node.className = value;
        else if (key === "html") node.innerHTML = value;
        else if (key === "text") node.textContent = value;
        else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
        else if (value !== null && value !== undefined) node.setAttribute(key, value);
      }
    }
    for (const kid of [].concat(kids || [])) {
      if (kid === null || kid === undefined || kid === false) continue;
      node.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
    }
    return node;
  }

  function toast(message) {
    toastBox.textContent = message;
    toastBox.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastBox.classList.remove("show"), 2200);
  }

  const button = (label, onClick, opts) => {
    opts = opts || {};
    const node = el("button", {
      class: opts.class || (opts.primary ? "btn--primary" : ""),
      onclick: onClick,
    }, [el("span", { text: label }), opts.sub ? el("span", { class: "sub", text: opts.sub }) : null]);
    if (opts.disabled) node.disabled = true;
    return node;
  };

  const rowButton = (label, sub, onClick, opts) => {
    opts = opts || {};
    const node = el("button", { class: "btn--row " + (opts.class || ""), onclick: onClick }, [
      el("span", { text: label }),
      sub ? el("span", { class: "sub", text: sub }) : null,
    ]);
    if (opts.disabled) node.disabled = true;
    return node;
  };

  /* ── 공통 조각 ─────────────────────────────────────────── */

  function statusBar() {
    if (!hero) return el("div", { class: "status" }, [el("div", { class: "status__name", text: "엘리멘탈 테이머" })]);
    return el("div", { class: "status" }, [
      el("div", { class: "status__top" }, [
        el("span", { class: "status__name", text: hero.name }),
        el("span", { class: "status__rank", text: G.rankName(hero) }),
        el("span", { class: "chip el-" + hero.element, text: hero.element + "속성" }),
      ]),
      el("div", { class: "status__row" }, [
        el("span", { html: `Lv <b>${hero.level}</b>` }),
        el("span", { html: `골드 <b>${hero.gold}</b>` }),
        el("span", { html: `파티 <b>${G.usedPoints(hero)}/${G.partyPoints(hero)}</b>` }),
        el("span", { html: `RP <b>${hero.rankPoints}</b>` }),
        el("span", { html: `섬 <b>${hero.islandLevel}</b>` }),
        el("span", { html: `<b>${hero.day}</b>일차` }),
      ]),
    ]);
  }

  function bar(value, max, extraClass) {
    const ratio = Math.max(0, Math.min(1, value / Math.max(1, max)));
    const low = ratio <= 0.3 ? " bar--low" : "";
    return el("div", { class: "bar " + (extraClass || "") + low },
      [el("i", { style: `width:${ratio * 100}%` })]);
  }

  function monsterCard(m, opts) {
    opts = opts || {};
    const sp = G.speciesOf(m);
    const kids = [
      el("div", { class: "mon__head" }, [
        el("span", { class: "mon__name", text: (m.evolved ? "★ " : "") + sp.name }),
        el("span", { class: "mon__lv", text: `Lv${m.level}` }),
      ]),
      el("div", { class: "meta" }, [
        el("span", { class: "chip el-" + sp.element, text: sp.element }),
        el("span", { class: "grade", text: sp.grade }),
        el("span", { text: `HP ${m.hp}/${G.maxHp(m)}` }),
        opts.compact ? null : el("span", { text: `SP ${m.sp}/${G.maxSp(m)}` }),
        opts.compact ? null : el("span", { text: `파티 ${G.partyCost(m)}` }),
      ]),
      bar(m.hp, G.maxHp(m)),
    ];
    if (!opts.compact) {
      kids.push(bar(m.sp, G.maxSp(m), "bar--sp"));
      kids.push(el("div", { class: "meta" }, [
        el("span", { text: `BRAIN ${m.brain}` }),
        el("span", { text: `FOOD ${m.food}` }),
        el("span", { text: `FEEL ${m.feel}/${G.B.condition.feel_max}` }),
        el("span", { text: sp.active_skill.name }),
      ]));
      if (m.passives.length) {
        kids.push(el("div", { class: "tags" }, m.passives.map((l) =>
          el("span", { class: "tag", text: `${G.passiveById(l.passive_id).name} ${l.level}` }))));
      }
    }
    return el("div", { class: "mon el-" + sp.element, style: `--el: var(--${elementVar(sp.element)})` }, kids);
  }

  const ELEMENT_VAR = { "수": "water", "화": "fire", "목": "wood", "풍": "wind", "광": "light", "악": "dark" };
  const elementVar = (element) => ELEMENT_VAR[element] || "line";

  /* ── 화면 틀 ───────────────────────────────────────────── */

  function paint(view) {
    app.replaceChildren();
    app.appendChild(view.status === false ? el("div") : statusBar());
    const main = el("main", {}, view.body || []);
    app.appendChild(main);
    if (view.dock && view.dock.length) {
      app.appendChild(el("div", { class: "dock " + (view.dockClass || "") }, view.dock));
    }
    if (view.scrollBottom) main.scrollTop = main.scrollHeight;
  }

  function go(builder) { stack.push(builder); paint(builder()); }
  function replace(builder) { stack[stack.length - 1] = builder; paint(builder()); }
  function refresh() { paint(stack[stack.length - 1]()); }
  function back() {
    if (stack.length > 1) stack.pop();
    paint(stack[stack.length - 1]());
  }
  const backButton = () => button("← 돌아가기", back, { class: "btn--ghost" });

  function section(title, kids) {
    return el("section", { class: "list" }, [title ? el("h2", { text: title }) : null].concat(kids));
  }

  /* ── 타이틀 · 캐릭터 만들기 ─────────────────────────────── */

  function titleScreen() {
    const saved = G.loadGame();
    return {
      status: false,
      body: [
        el("div", { class: "card center", style: "gap:14px;padding:26px 16px;margin-top:8vh" }, [
          el("div", { class: "eyebrow", text: "턴제 몬스터 육성" }),
          el("h1", { text: "엘리멘탈 테이머" }),
          el("p", { class: "muted", text: "몬스터를 잡고 · 기르고 · 합쳐서 강해진다. 132종, 6속성." }),
        ]),
      ],
      dock: [
        saved ? button("이어하기", () => {
          hero = saved;
          stack = [];
          go(hubScreen);
        }, { primary: true, sub: `${saved.name} · Lv${saved.level} · ${saved.day}일차` }) : null,
        button(saved ? "새로 시작하기" : "시작하기", () => {
          if (saved && !confirm("저장된 기록을 지우고 새로 시작할까요?")) return;
          go(createScreen);
        }, { primary: !saved }),
      ].filter(Boolean),
    };
  }

  function createScreen() {
    const nameInput = el("input", {
      type: "text", placeholder: "카이", maxlength: "8",
      style: "width:100%;font:inherit;color:inherit;background:var(--surface-2);" +
        "border:1px solid var(--line);border-radius:10px;padding:12px;min-height:46px",
    });
    let element = null;

    const elementButtons = el("div", { class: "list" }, G.ELEMENTS.map((name) =>
      button(`${name}속성`, () => { element = name; refreshPick(); },
        { sub: G.SPECIES.length && D.roster.elements[name] })));

    function refreshPick() {
      [...elementButtons.children].forEach((node, i) => {
        node.style.borderColor = G.ELEMENTS[i] === element ? "var(--ember)" : "";
      });
    }

    return {
      status: false,
      body: [
        section("이름", [nameInput]),
        section("속성", [
          el("p", { class: "muted", text: "같은 속성 몬스터는 포획 확률과 교감도가 유리하다. 능력치 총합은 속성마다 같다." }),
          elementButtons,
        ]),
      ],
      dock: [
        button("파트너 고르기 →", () => {
          if (!element) { toast("속성을 고르세요."); return; }
          const name = (nameInput.value || "").trim() || "카이";
          go(() => starterScreen(name, element));
        }, { primary: true }),
        backButton(),
      ],
    };
  }

  function starterScreen(name, element) {
    const starters = G.filterSpecies(element, "common");
    return {
      status: false,
      body: [
        section("첫 파트너", starters.map((sp) =>
          rowButton(sp.name, `${sp.active_skill.name} · ${sp.active_skill.description}`, () => {
            hero = G.makeHero(name, element);
            const starter = G.makeMonster(G.byName(sp.name), 5);
            hero.party.push(starter);
            hero.seen.push(sp.name);
            G.saveGame(hero);
            stack = [];
            go(hubScreen);
            toast(`${name}(은)는 ${sp.name}(와)과 함께 길을 나섰다.`);
          }))),
      ],
      dock: [backButton()],
    };
  }

  /* ── 허브 ──────────────────────────────────────────────── */

  function hubScreen() {
    const lead = hero.party[0];
    return {
      body: [
        lead ? monsterCard(lead) : null,
        section(null, [
          rowButton("파티 · 도감", `${hero.party.length}마리 · 도감 ${hero.seen.length}/${G.SPECIES.length}`, () => go(partyScreen)),
          rowButton("공방", "조합 · 강화 · 패시브", () => go(workshopScreen)),
          rowButton("배틀존", `RP ${hero.rankPoints} · ${hero.wins}승 ${hero.losses}패`, () => go(zoneScreen)),
          rowButton("몬스터마트", "몬스터를 사고판다", () => go(marketScreen)),
          rowButton("우체통", "하루 한 번 선물", () => go(mailScreen)),
          rowButton("미지의 섬", `섬 Lv${hero.islandLevel}`, () => go(islandScreen)),
          rowButton("상점", `골드 ${hero.gold}`, () => go(shopScreen)),
        ]),
      ].filter(Boolean),
      dockClass: "dock--two",
      dock: [
        el("div", { class: "span-all" }, [
          button("사냥하기", () => go(huntScreen), { primary: true, sub: "몬스터를 만나고 잡는다" }),
        ]),
        button("쉬기 (다음 날로)", () => {
          hero.party.forEach(G.restMonster);
          hero.party.forEach((m) => { m.food = G.B.condition.food_max; });
          hero.day += 1;
          G.saveGame(hero);
          refresh();
          toast(`하룻밤 쉬었다. ${hero.day}일차.`);
        }, { sub: "전체 회복" }),
        button("저장하고 타이틀로", () => {
          G.saveGame(hero);
          stack = [];
          go(titleScreen);
        }, { class: "btn--ghost" }),
      ],
    };
  }

  /* ── 사냥 ──────────────────────────────────────────────── */

  function matchupHint(area) {
    if (!hero.party.length || area.element === "전속성") return "";
    const multiplier = G.elementMultiplier(G.monElement(hero.party[0]), area.element);
    if (multiplier > 1) return " · 유리";
    if (multiplier < 1) return " · 불리";
    return "";
  }

  function huntScreen() {
    // 해금 기준은 주인공이 아니라 파티 전력이다. 주인공이 먼저 크기 때문이다.
    const power = Math.max(...hero.party.map((m) => m.level), hero.level);
    const areas = G.AREAS.filter((a) => a.minLevel <= power + 4);
    return {
      body: [section("어디로 갈까", areas.map((area) =>
        rowButton(area.name,
          `${area.element}속성 · Lv${area.minLevel}~${area.maxLevel}${matchupHint(area)}`,
          () => startHunt(area, false, hero.islandLevel))))],
      dock: [backButton()],
    };
  }

  function startHunt(area, visiting, islandLevel) {
    if (!G.alivePartyOf(hero).length) { toast("싸울 수 있는 몬스터가 없다. 쉬어야 한다."); return; }
    fight = G.makeBattle(hero, G.spawn(area, hero, islandLevel));
    fight.area = area;
    fight.visiting = visiting;
    pending = [];
    go(battleScreen);
  }

  /* ── 전투 ──────────────────────────────────────────────── */

  function battleScreen() {
    const body = [
      section(null, fight.enemies.map((m) => monsterCard(m, { compact: true }))),
      el("div", { class: "eyebrow", text: "내 파티" }),
      section(null, fight.allies.map((m) => monsterCard(m, { compact: true }))),
      fight.log.length ? el("div", { class: "card log" }, fight.log.slice(-40).map((line) =>
        el("p", { class: [line.kind, line.side ? "by-" + line.side : ""].join(" ").trim(), text: line.text }))) : null,
    ].filter(Boolean);

    if (fight.result) {
      return {
        body,
        scrollBottom: true,
        dock: [button("계속", () => {
          const wasIsland = fight.area && fight.area.island;
          if (wasIsland && (fight.result === "win" || fight.result === "captured")) {
            const gain = fight.enemies.reduce((sum, m) => sum + m.level, 0) * 3;
            for (const line of G.islandGain(hero, gain, fight.visiting)) fight.log.push(line);
          }
          G.saveGame(hero);
          fight = null;
          back();
        }, { primary: true })],
      };
    }

    const actor = G.livingIn(fight.allies)[pending.length];
    if (!actor) { setTimeout(runPendingRound, 0); return { body, scrollBottom: true, dock: [] }; }

    const many = G.livingIn(fight.allies).length > 1;
    return {
      body,
      scrollBottom: true,
      dockClass: "dock--two dock--compact",
      dock: [
        many ? el("div", { class: "span-all eyebrow", text: `${G.monName(actor)}의 차례` }) : null,
        button("물리 공격", () => command(actor, "attack")),
        button(G.speciesOf(actor).active_skill.name, () => command(actor, "skill"),
          { sub: `SP ${G.spCost(actor)}` }),
        button("방어", () => command(actor, "guard")),
        button("아이템", () => go(() => itemPicker(actor))),
        button("포획", () => go(() => ballPicker(actor))),
        button("도망", () => command(actor, "flee")),
        button("자동 전투로 끝까지", () => {
          fight.auto = true;
          pending = [];
          runAuto();
        }, { primary: true, class: "btn--primary span-all", sub: "경험치 60%" }),
      ].filter(Boolean),
    };
  }

  function command(actor, kind, item) {
    const foes = G.livingIn(fight.enemies);
    if ((kind === "attack" || kind === "skill" || kind === "capture") && foes.length > 1) {
      go(() => targetPicker(actor, kind, item));
      return;
    }
    pending.push({ kind, actor, target: foes[0] || null, item });
    refresh();
  }

  function targetPicker(actor, kind, item) {
    return {
      body: [section("누구를 노릴까", G.livingIn(fight.enemies).map((foe) =>
        rowButton(G.monName(foe), `Lv${foe.level} · HP ${foe.hp}/${G.maxHp(foe)}`, () => {
          pending.push({ kind, actor, target: foe, item });
          back();
          refresh();
        })))],
      dock: [backButton()],
    };
  }

  function itemPicker(actor) {
    const usable = Object.keys(hero.items).filter((n) => hero.items[n] > 0 && (D.items[n] || {}).effect);
    return {
      body: [usable.length
        ? section("무엇을 쓸까", usable.map((name) =>
          rowButton(name, `x${hero.items[name]}`, () => {
            pending.push({ kind: "item", actor, item: name });
            back();
            refresh();
          })))
        : el("p", { class: "muted", text: "쓸 수 있는 아이템이 없다." })],
      dock: [backButton()],
    };
  }

  function ballPicker(actor) {
    const balls = Object.keys(hero.items).filter((n) => hero.items[n] > 0 && (D.items[n] || {}).capture_bonus);
    return {
      body: [balls.length
        ? section("어떤 볼로", balls.map((name) => {
          const target = G.livingIn(fight.enemies)[0];
          const chance = Math.round(G.captureChance(target, hero, name, actor) * 100);
          return rowButton(name, `x${hero.items[name]} · 성공률 약 ${chance}%`, () => {
            back();
            command(actor, "capture", name);
          });
        }))
        : el("p", { class: "muted", text: "몬스터볼이 없다. 상점에서 살 수 있다." })],
      dock: [backButton()],
    };
  }

  function runPendingRound() {
    G.runRound(fight, pending);
    pending = [];
    if (fight.result) G.finishBattle(fight);
    refresh();
  }

  function runAuto() {
    let guard = 0;
    while (!fight.result && guard++ < 80) {
      G.runRound(fight, G.livingIn(fight.allies).map((a) => G.autoAction(fight, a)));
    }
    G.finishBattle(fight);
    refresh();
  }

  /* ── 파티 · 도감 ───────────────────────────────────────── */

  function partyScreen() {
    return {
      body: [
        section("파티", hero.party.map((m) =>
          el("div", { onclick: () => go(() => monsterScreen(m)) }, [monsterCard(m)]))),
        hero.storage.length ? section("보관함", hero.storage.map((m) =>
          el("div", { onclick: () => go(() => monsterScreen(m)) }, [monsterCard(m, { compact: true })]))) : null,
      ].filter(Boolean),
      dock: [
        button("도감 보기", () => go(bookScreen), { sub: `${hero.seen.length}/${G.SPECIES.length}종` }),
        backButton(),
      ],
    };
  }

  function monsterScreen(m) {
    const inParty = hero.party.includes(m);
    const healables = Object.keys(hero.items).filter((n) => hero.items[n] > 0 && (D.items[n] || {}).effect);
    const marbles = Object.keys(hero.items).filter((n) => hero.items[n] > 0 && n.startsWith("마블-"));
    return {
      body: [
        monsterCard(m),
        section("능력치", [el("div", { class: "card" }, G.STATS.map((key) =>
          el("div", { class: "meta", style: "justify-content:space-between" }, [
            el("span", { text: G.STAT_LABEL[key] }),
            el("span", { text: String(G.stat(m, key)) }),
          ])))]),
        section("돌보기", [
          rowButton(inParty ? "보관함으로 보내기" : "파티에 넣기", `파티 포인트 ${G.partyCost(m)}`, () => {
            if (inParty) {
              if (hero.party.length === 1) { toast("파티가 비면 사냥할 수 없다."); return; }
              hero.party.splice(hero.party.indexOf(m), 1);
              hero.storage.push(m);
            } else if (G.usedPoints(hero) + G.partyCost(m) <= G.partyPoints(hero)) {
              hero.storage.splice(hero.storage.indexOf(m), 1);
              hero.party.push(m);
            } else { toast("파티 포인트가 모자란다."); return; }
            G.saveGame(hero);
            back();
            refresh();
          }),
          rowButton("회복 아이템 쓰기", healables.length ? healables.join(", ") : "없음", () => {
            if (!healables.length) { toast("회복 아이템이 없다."); return; }
            go(() => healScreen(m, healables));
          }, { disabled: !healables.length }),
          rowButton("마블 먹이기", marbles.length ? "허기도와 교감도가 오른다" : "마블이 없다", () => {
            if (!marbles.length) { toast("상점에서 마블을 살 수 있다."); return; }
            go(() => feedScreen(m, marbles));
          }, { disabled: !marbles.length }),
        ]),
      ],
      dock: [backButton()],
    };
  }

  function healScreen(m, items) {
    return {
      body: [section("무엇을 쓸까", items.map((name) =>
        rowButton(name, `x${hero.items[name]}`, () => {
          const effect = D.items[name].effect;
          if (effect.revive && G.alive(m)) { toast(`${G.monName(m)}(은)는 멀쩡하다.`); return; }
          if (effect.hp && G.alive(m) && m.hp >= G.maxHp(m)) { toast("HP가 이미 가득하다."); return; }
          G.takeItem(hero, name);
          if (effect.revive && !G.alive(m)) { m.hp = Math.floor(G.maxHp(m) * effect.revive); toast("부활했다."); }
          if (effect.hp && G.alive(m)) {
            const healed = Math.min(effect.hp, G.maxHp(m) - m.hp);
            m.hp += healed;
            toast(`HP ${healed} 회복`);
          }
          if (effect.sp) {
            const healed = Math.min(effect.sp, G.maxSp(m) - m.sp);
            m.sp += healed;
            if (!effect.hp) toast(`SP ${healed} 회복`);
          }
          G.saveGame(hero);
          back();
          refresh();
        })))],
      dock: [backButton()],
    };
  }

  function feedScreen(m, marbles) {
    return {
      body: [section("어떤 마블을", marbles.map((name) =>
        rowButton(name, `x${hero.items[name]}`, () => {
          G.takeItem(hero, name);
          m.food = Math.min(G.B.condition.food_max, m.food + 40);
          const element = name.split("-")[1];
          const out = [];
          const gain = element === G.monElement(m) ? G.B.condition.feel_per_marble : 10;
          m.feel += gain;
          if (m.feel >= G.B.condition.feel_max && !m.evolved) {
            m.feel = 0;
            m.evolved = true;
            m.hp = G.maxHp(m);
            out.push("진화했다!");
          }
          G.saveGame(hero);
          back();
          refresh();
          toast(out.length ? out[0] : `허기도와 교감도가 올랐다. (FEEL ${m.feel})`);
        })))],
      dock: [backButton()],
    };
  }

  function bookScreen() {
    const rows = G.GRADES.map((grade) => {
      const names = G.filterSpecies(null, grade).filter((s) => hero.seen.includes(s.name)).map((s) => s.name);
      const total = G.filterSpecies(null, grade).length;
      return el("div", { class: "card" }, [
        el("div", { class: "meta", style: "justify-content:space-between" }, [
          el("span", { class: "grade", text: grade }),
          el("span", { text: `${names.length}/${total}` }),
        ]),
        el("p", { class: "muted", text: names.length ? names.join(", ") : "아직 만난 적 없다." }),
      ]);
    });
    return { body: [section(`도감 ${hero.seen.length}/${G.SPECIES.length}`, rows)], dock: [backButton()] };
  }

  /* ── 공방 ──────────────────────────────────────────────── */

  function workshopScreen() {
    return {
      body: [section(null, [
        rowButton("몬스터 조합", "같은 등급 둘을 합쳐 위를 노린다", () => go(() => fusePick(null))),
        rowButton("몬스터 강화", "BRAIN을 올려 능력치를 높인다", () => go(enhancePick)),
        rowButton("패시브 스킬", "재료를 들여 능력을 붙인다", () => go(passivePick)),
      ])],
      dock: [backButton()],
    };
  }

  function fusePick(first) {
    const pool = G.allMonsters(hero).filter((m) => m !== first &&
      (!first || G.speciesOf(m).grade === G.speciesOf(first).grade));
    if (!first) {
      return {
        body: [section("재료 1", pool.map((m) =>
          rowButton(G.monName(m), `${G.speciesOf(m).grade} Lv${m.level}`, () => replace(() => fusePick(m)))))],
        dock: [backButton()],
      };
    }
    const grade = G.speciesOf(first).grade;
    const catalyst = hero.items["조합촉매"] > 0;
    return {
      body: [
        el("div", { class: "card" }, [
          el("div", { class: "eyebrow", text: "재료 1" }),
          el("div", { text: `${G.monName(first)} · ${grade} Lv${first.level}` }),
          el("p", { class: "muted", text: `성공률 ${Math.round(G.fusionRate(grade) * 100)}%` +
            (catalyst ? ` (촉매 사용 시 ${Math.round(G.fusionRate(grade, true) * 100)}%)` : "") +
            ` · 비용 ${G.fusionCost(grade)}골드 · 실패하면 한 등급 아래가 나온다` }),
        ]),
        section("재료 2 (같은 등급)", pool.length ? pool.map((m) =>
          rowButton(G.monName(m), `Lv${m.level}`, () => {
            const messages = G.fuse(hero, first, m, catalyst);
            G.saveGame(hero);
            back();
            refresh();
            toast(messages.join(" "));
          })) : [el("p", { class: "muted", text: `${grade} 등급 짝이 없다.` })]),
      ],
      dock: [backButton()],
    };
  }

  function enhancePick() {
    const catalyst = hero.items["강화촉매"] > 0;
    return {
      body: [section("어느 몬스터를", G.allMonsters(hero).map((m) =>
        rowButton(G.monName(m),
          `BRAIN ${m.brain} · 성공률 ${Math.round(G.enhanceRate(m, catalyst) * 100)}% · ${G.enhanceCost(m)}골드`,
          () => {
            const messages = G.enhance(hero, m, catalyst);
            G.saveGame(hero);
            refresh();
            toast(messages.join(" "));
          })))],
      dock: [backButton()],
    };
  }

  function passivePick() {
    return {
      body: [section("어느 몬스터에게", G.allMonsters(hero).map((m) =>
        rowButton(G.monName(m), `슬롯 ${m.passives.length}/${G.slotLimit(m)}`,
          () => go(() => passiveList(m)))))],
      dock: [backButton()],
    };
  }

  function passiveList(m) {
    const rows = D.passives.map((p) => {
      const level = G.passiveLevel(m, p.id);
      if (level >= p.levels.length) return null;
      const { gold, materials } = G.attachCost(m, p.id);
      const need = Object.entries(materials).map(([k, v]) => `${k} ${v}`).join(", ");
      return rowButton(`${p.name}${level ? ` Lv${level}→${level + 1}` : ""}`,
        `${p.description} · ${gold}골드 · ${need}`, () => {
          const messages = G.attachPassive(hero, m, p.id);
          G.saveGame(hero);
          refresh();
          toast(messages.join(" "));
        });
    }).filter(Boolean);
    return {
      body: [
        monsterCard(m),
        section("배울 수 있는 패시브", rows.length ? rows : [el("p", { class: "muted", text: "더 배울 것이 없다." })]),
      ],
      dock: [backButton()],
    };
  }

  /* ── 배틀존 · 마트 · 우체통 · 섬 · 상점 ────────────────── */

  function zoneScreen() {
    const start = (mode) => {
      if (!G.alivePartyOf(hero).length) { toast("싸울 수 있는 몬스터가 없다."); return; }
      const rival = G.makeRival(hero);
      fight = G.makeBattle(hero, rival.party.map((m) => {
        const copy = G.makeMonster(m.species, m.level);
        copy.brain = m.brain;
        return copy;
      }), { capturable: false, mode, rival });
      pending = [];
      go(battleScreen);
      toast(`${mode}: ${rival.name}`);
    };
    return {
      body: [
        section(null, [
          rowButton("퀵배틀", "범위 안에서 상대가 정해진다 · 랭킹 반영", () => start("퀵배틀")),
          rowButton("랭킹배틀", "이기면 길드 랭킹이 올라 파티 포인트가 는다", () => start("랭킹배틀")),
          rowButton("친선배틀", "랭킹에 반영되지 않는다", () => start("친선배틀")),
        ]),
        section("배틀로그", hero.log.length
          ? hero.log.slice(0, 10).map((r) => el("div", { class: "card" }, [
            el("div", { class: "meta", style: "justify-content:space-between" }, [
              el("span", { text: `${r.day}일차 ${r.mode}` }),
              el("span", { text: `${r.result} ${r.delta > 0 ? "+" : ""}${r.delta}` }),
            ]),
            el("div", { class: "muted", text: r.opponent }),
          ]))
          : [el("p", { class: "muted", text: "아직 기록이 없다." })]),
      ],
      dock: [backButton()],
    };
  }

  function marketScreen() {
    const listings = G.marketListings(hero);
    return {
      body: [
        section("매물 (하루에 한 번 바뀐다)", listings.map((listing) =>
          rowButton(G.monName(listing.monster),
            `${G.speciesOf(listing.monster).grade} Lv${listing.monster.level} · ${listing.price}골드`,
            () => {
              if (hero.gold < listing.price) { toast("골드가 모자란다."); return; }
              hero.gold -= listing.price;
              const message = G.catchMonster(hero, listing.monster);
              hero.market = listings.filter((l) => l !== listing);
              G.saveGame(hero);
              refresh();
              toast(message);
            }))),
        section("내 몬스터 팔기", G.allMonsters(hero).map((m) =>
          rowButton(G.monName(m),
            `Lv${m.level} · ${Math.floor(G.marketPrice(m) * G.B.network.market_sell_ratio)}골드`, () => {
              if (hero.party.includes(m) && hero.party.length === 1) { toast("마지막 파티 몬스터는 팔 수 없다."); return; }
              const price = Math.floor(G.marketPrice(m) * G.B.network.market_sell_ratio);
              hero.gold += price;
              const list = hero.party.includes(m) ? hero.party : hero.storage;
              list.splice(list.indexOf(m), 1);
              G.saveGame(hero);
              refresh();
              toast(`${price}골드에 팔았다.`);
            }))),
      ],
      dock: [backButton()],
    };
  }

  function mailScreen() {
    const ready = hero.lastGiftDay < hero.day;
    return {
      body: [
        el("div", { class: "card" }, [
          el("h2", { text: "우체통" }),
          el("p", { class: "muted", text: ready ? "오늘 받을 선물이 있다." : "오늘 선물은 이미 받았다. 쉬면 다시 찬다." }),
        ]),
        section("소지품", Object.entries(hero.items).map(([name, count]) =>
          el("div", { class: "card" }, [el("div", { class: "meta", style: "justify-content:space-between" }, [
            el("span", { text: name }), el("span", { text: `x${count}` })])]))),
      ],
      dock: [
        button("선물 받기", () => {
          if (!ready) { toast("오늘 선물은 이미 받았다."); return; }
          hero.lastGiftDay = hero.day;
          const names = [];
          for (let i = 0; i < G.B.network.mailbox_gifts_per_day; i++) {
            const item = G.pick(G.B.network.mailbox_gift_pool);
            G.addItem(hero, item, 1);
            names.push(item);
          }
          G.saveGame(hero);
          refresh();
          toast("친구들이 보낸 " + names.join(", ") + "(을)를 받았다.");
        }, { primary: true, disabled: !ready }),
        backButton(),
      ],
    };
  }

  function islandScreen() {
    const ready = hero.lastChestDay < hero.day;
    const cap = G.GRADES[G.islandGradeCap(hero.islandLevel)];
    return {
      body: [
        el("div", { class: "card" }, [
          el("h2", { text: "미지의 섬" }),
          el("p", { class: "muted", text:
            `섬 Lv${hero.islandLevel} · 지금 ${cap} 등급까지 나온다. 섬 레벨 ` +
            `${G.B.island.party_point_levels.join(", ")}에서 파티 포인트가 는다.` }),
        ]),
        section(null, [
          rowButton("내 섬에서 사냥", "주인공과 비슷한 레벨이 등급 상관없이 나온다",
            () => startHunt(G.ISLAND, false, hero.islandLevel)),
          rowButton("친구의 섬 방문", `경험치 ${G.B.island.visit_experience_bonus}배`,
            () => startHunt(G.ISLAND, true, hero.islandLevel + G.randInt(2, 10))),
        ]),
      ],
      dock: [
        button("보물상자 열기", () => {
          if (!ready) { toast("오늘 보물상자는 이미 열었다."); return; }
          hero.lastChestDay = hero.day;
          const gold = G.randInt(100, 300) * Math.max(1, Math.floor(hero.islandLevel / 5));
          hero.gold += gold;
          const names = [];
          for (let i = 0; i < 2; i++) {
            const item = G.pick(G.B.network.mailbox_gift_pool);
            G.addItem(hero, item, 1);
            names.push(item);
          }
          G.saveGame(hero);
          refresh();
          toast(`골드 ${gold}, ${names.join(", ")}(을)를 얻었다.`);
        }, { primary: true, disabled: !ready }),
        backButton(),
      ],
    };
  }

  function shopScreen() {
    const stock = Object.entries(D.items).filter(([, entry]) =>
      ["소비", "볼", "보조", "먹이"].includes(entry.category));
    return {
      body: [section("상점", stock.map(([name, entry]) =>
        rowButton(name, `${entry.price}골드 · ${entry.category}${hero.items[name] ? ` · 보유 ${hero.items[name]}` : ""}`,
          () => {
            if (hero.gold < entry.price) { toast("골드가 모자란다."); return; }
            hero.gold -= entry.price;
            G.addItem(hero, name, 1);
            G.saveGame(hero);
            refresh();
            toast(`${name}(을)를 샀다.`);
          })))],
      dock: [backButton()],
    };
  }

  /* ── 시작 ──────────────────────────────────────────────── */

  go(titleScreen);
})();

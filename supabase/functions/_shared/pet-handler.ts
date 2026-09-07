import { advance, care, newPet, type Pet, type Action } from './pet.ts';

export type Save = { state: Pet; revision: number };
export type PetServices = {
  authenticate(request: Request): Promise<string | null>;
  ensure(id: string, initial: Pet): Promise<void>;
  read(id: string): Promise<Save>;
  write(id: string, revision: number, state: Pet): Promise<boolean>;
  now(): number;
  roll(): number;
};
const reply = (body: unknown, status = 200) => Response.json(body, {
  status, headers: { 'Cache-Control': 'private, no-store' },
});
const actions = new Set(['feed', 'mist', 'clean', 'play', 'save', 'rename', 'warm', 'hatch', 'newEgg', 'select']);

export function createPetHandler(services: PetServices) {
  return async (request: Request): Promise<Response> => {
    if (!['GET', 'POST'].includes(request.method)) return reply({ error: '허용되지 않은 요청이에요.' }, 405);
    try {
      const owner = await services.authenticate(request);
      if (!owner) return reply({ error: '로그인 후 크레를 만날 수 있어요.' }, 401);
      if (request.method === 'GET') {
        await services.ensure(owner, newPet(services.now()));
        const saved = await services.read(owner);
        return reply({ pet: advance(saved.state, services.now()), revision: saved.revision });
      }
      if (Number(request.headers.get('content-length') || 0) > 4096) return reply({ error: '입력 내용이 너무 길어요.' }, 413);
      const raw = await request.text();
      if (new TextEncoder().encode(raw).length > 4096) return reply({ error: '입력 내용이 너무 길어요.' }, 413);
      let body: Record<string, unknown>;
      try { body = JSON.parse(raw); } catch { return reply({ error: '입력 내용을 확인해 주세요.' }, 400); }
      if (!body || !actions.has(String(body.action)) || !Number.isSafeInteger(body.revision) || Number(body.revision) < 0 ||
        (body.action === 'rename' && (typeof body.name !== 'string' || !body.name.trim() || body.name.length > 12)) ||
        (body.action === 'select' && (typeof body.name !== 'string' || body.name.length > 80))) {
        return reply({ error: '입력 내용을 확인해 주세요.' }, 400);
      }
      const saved = await services.read(owner);
      const conflict = async () => {
        const current = await services.read(owner);
        return reply({ error: '다른 창의 기록을 불러왔어요. 다시 눌러 주세요.', pet: advance(current.state, services.now()), revision: current.revision }, 409);
      };
      if (saved.revision !== body.revision) return conflict();
      // A client supplies only an action, never a pet state, owner, clock, or hatch result.
      const result = care(saved.state, body.action as Action, services.now(),
        typeof body.name === 'string' ? body.name : undefined,
        body.action === 'hatch' ? services.roll() : undefined);
      if (!await services.write(owner, saved.revision, result.pet)) return conflict();
      return reply({ ...result, revision: saved.revision + 1 });
    } catch {
      console.error('Cre terrarium request failed');
      return reply({ error: '크레의 기록을 연결하지 못했어요. 다시 불러와 주세요.' }, 503);
    }
  };
}

import { createClient } from 'npm:@supabase/supabase-js@2.115.0';
import { createPetHandler, type Save } from '../_shared/pet-handler.ts';

const options = { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } };
const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, options);

Deno.serve(createPetHandler({
  async authenticate(request) {
    const authorization = request.headers.get('authorization') || '';
    if (!authorization.startsWith('Bearer ')) return null;
    // Validate with Supabase Auth, including ES256 tokens. Never trust decoded claims alone.
    const { data: { user }, error } = await admin.auth.getUser(authorization.slice(7));
    if (error || !user) return null;
    const { data: account, error: lookupError } = await admin.from('cre_accounts').select('id').eq('id', user.id).maybeSingle();
    if (lookupError) throw lookupError;
    return account?.id ?? null;
  },
  async ensure(user_id, state) {
    const { error } = await admin.from('cre_terrarium_saves').upsert({ user_id, state, revision: 0 }, { onConflict: 'user_id', ignoreDuplicates: true });
    if (error) throw error;
  },
  async read(id) {
    const { data, error } = await admin.from('cre_terrarium_saves').select('state, revision').eq('user_id', id).single();
    if (error || !data) throw error || new Error('Save missing');
    return data as Save;
  },
  async write(id, revision, state) {
    const { data, error } = await admin.from('cre_terrarium_saves')
      .update({ state, revision: revision + 1, updated_at: new Date().toISOString() })
      .eq('user_id', id).eq('revision', revision).select('revision');
    if (error) throw error;
    return data.length === 1;
  },
  now: () => Date.now(),
  roll: () => crypto.getRandomValues(new Uint32Array(1))[0] / 4294967296,
}));

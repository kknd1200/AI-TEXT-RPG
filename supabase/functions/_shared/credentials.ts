export const USERNAME_PATTERN = /^[a-z0-9_]{4,20}$/;

export function normalizeUsername(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

export function validateCredentials(username: unknown, password: unknown, signup: boolean): string | null {
  if (!USERNAME_PATTERN.test(normalizeUsername(username))) return '아이디는 영문 소문자·숫자·밑줄(_)로 4~20자 입력해 주세요.';
  if (typeof password !== 'string' || password.length < 8 || new TextEncoder().encode(password).length > 72) return '비밀번호는 8자 이상, 영문 기준 72자 이내로 입력해 주세요.';
  if (signup && (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password))) return '비밀번호에 영문과 숫자를 함께 넣어 주세요.';
  return null;
}

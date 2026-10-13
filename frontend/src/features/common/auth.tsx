// 로그인 상태 (CM-01, API 명세서 A-2, A-4). 로그아웃은 넣지 않음 (10/6 결정)
// 앱을 켜면 재발급권이 저장돼 있는지로 상태를 정함. 출입증이 끝났으면 API를 부를 때 api()가 알아서 다시 받음
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, setAuthLostHandler } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { tokens } from '@/shared/storage/tokens';

// 서버 app/models/users.py와 같게 (5번 틀리면 10분 잠김)
export const LOGIN_MAX_FAILURES = 5;
export const LOGIN_LOCK_MINUTES = 10;

export type User = { id: number; nickname: string | null; birthYear: number; sex: 'M' | 'F' };
type LoginResponse = { accessToken: string; refreshToken: string; user: User };

type Status = 'checking' | 'signedOut' | 'signedIn';
type Auth = {
  status: Status;
  notice: string | null; // 로그인 화면 위에 띄울 안내 (로그인이 끝났을 때)
  login: (email: string, password: string) => Promise<void>;
};

const Ctx = createContext<Auth | null>(null);

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth는 AuthProvider 안에서만 쓸 수 있어요');
  return v;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('checking');
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    tokens
      .getRefresh()
      .then((refresh) => setStatus(refresh ? 'signedIn' : 'signedOut'))
      .catch(() => setStatus('signedOut'));
    setAuthLostHandler((reason) => {
      setNotice(reason === 'expired' ? copy.login.expired : null);
      setStatus('signedOut');
    });
    return () => setAuthLostHandler(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<LoginResponse>('POST', '/auth/login', { email, password }, { auth: false });
    await tokens.save(res.accessToken, res.refreshToken);
    setNotice(null);
    setStatus('signedIn');
  }, []);

  const value = useMemo(() => ({ status, notice, login }), [status, notice, login]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

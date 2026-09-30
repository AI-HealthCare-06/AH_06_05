import React, { createContext, useContext, useMemo, useState } from 'react';
import { Warning, checkSafety } from './dur';
import { Rec, Rx, RxItem, sampleRecognition } from './scenario';

export type Route = { name: string; params?: any };
export type Tab = 'home' | 'today' | 'chat' | 'me';
export type Goal = Rec & { value: number; done: boolean };
export type ChatMsg = { id: string; role: 'user' | 'bot'; text: string; type?: string; chips?: string[]; source?: string; actions?: string[]; context?: string };
export type User = { name: string; email: string; birthYear: number; sex: 'M' | 'F' };

type State = {
  loggedIn: boolean;
  user: User;
  loginFails: number;
  lockedUntil: number | null;
  photos: string[];
  rxs: Rx[];
  items: RxItem[];
  analysis: null | { at: string; warnings: Warning[]; status: 'running' | 'done' | 'failed' };
  analysisDeleted: boolean;
  goals: Goal[];
  points: { today: number; week: number; total: number };
  streak: number;
  chat: ChatMsg[];
  chatContext: null | { kind: 'warning' | 'drug'; title: string; text?: string; source?: string };
  retentionDays: number;
  showIds: boolean;
};

const initial: State = {
  loggedIn: false,
  user: { name: '홍길동', email: 'hong@email.com', birthYear: 1958, sex: 'M' },
  loginFails: 0,
  lockedUntil: null,
  photos: [],
  rxs: [],
  items: [],
  analysis: null,
  analysisDeleted: false,
  goals: [],
  points: { today: 0, week: 90, total: 450 },
  streak: 2,
  chat: [],
  chatContext: null,
  retentionDays: 180,
  showIds: true,
};

type Ctx = {
  s: State;
  set: (p: Partial<State> | ((s: State) => Partial<State>)) => void;
  stack: Route[];
  tab: Tab;
  go: (name: string, params?: any) => void;
  replace: (name: string, params?: any) => void;
  back: () => void;
  toTab: (t: Tab) => void;
  resetAll: () => void;
  loadSample: () => void;
  runAnalysis: () => void;
};

const C = createContext<Ctx>(null as any);
export const useApp = () => useContext(C);

export const TODAY = { iso: '2026-09-29', label: '9월 29일 월요일', short: '9월 29일' };

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [s, setS] = useState<State>(initial);
  const [stack, setStack] = useState<Route[]>([]);
  const [tab, setTab] = useState<Tab>('home');

  const ctx = useMemo<Ctx>(() => {
    const set: Ctx['set'] = (p) => setS((prev) => ({ ...prev, ...(typeof p === 'function' ? p(prev) : p) }));
    return {
      s, set, stack, tab,
      go: (name, params) => setStack((st) => [...st, { name, params }]),
      replace: (name, params) => setStack((st) => [...st.slice(0, -1), { name, params }]),
      back: () => setStack((st) => st.slice(0, -1)),
      toTab: (t) => { setStack([]); setTab(t); },
      resetAll: () => { setS(initial); setStack([]); setTab('home'); },
      loadSample: () => { const r = sampleRecognition(); set({ rxs: r.rxs, items: r.items }); },
      runAnalysis: () => {
        const active = s.items.filter((i) => i.edi && (i.status === 'auto' || i.status === 'user_confirmed'));
        const warnings = checkSafety(active.map((i) => ({ edi: i.edi!, hospital: s.rxs.find((r) => r.id === i.rxId)?.hospital })), s.user.birthYear);
        set({ analysis: { at: TODAY.iso, warnings, status: 'running' }, analysisDeleted: false });
      },
    };
  }, [s, stack, tab]);

  return <C.Provider value={ctx}>{children}</C.Provider>;
}

// CB-01 대화 흐름 (설계 메모 3-4, 3-5, 4-3, 4-6, 4-7 항목, 명세서 H-1 ~ H-8)
// - 보내기: 대화가 없으면 H-1, (분석 번호만 받고 들어왔으면 H-7), H-3. 202 뒤 H-2를 2초마다 불러 답 줄이 done이 되면 그림
// - 보낸 때부터 30초가 지나거나 답 줄이 없어지면 E6. [다시 시도]는 같은 clientRequestId (서버가 같은 답 줄을 주거나 새로 만듦)
// - 질문 원문은 메모리에만 둠 (1층이 잡은 질문은 서버에 원문이 없음). 앱 로그에 남기지 않음
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '@/shared/api/client';

import { addContext, findToday, getMessages, sendQuestion, startSession } from './api';
import { newRequestId, nextKstMidnight } from './time';
import type { ChatContext, ChatParams, Message } from './types';

const POLL_MS = 2000;
const TIMEOUT_MS = 30_000; // 앱 시간 초과 (설계 메모 0-1 항목 7)

export type ErrorKind = 'general' | 'tooMany' | { message: string }; // message: 403처럼 다시 시도로 풀리지 않음

// 서버에 아직 닿지 않았거나 실패한 질문
export type Pending = {
  crid: string;
  content: string;
  dismissed: boolean; // [지금은 증상이 없어요] 뒤 다시 보낸 질문
  sentAt: number;
  answerId?: number;
  questionId?: number; // 서버 질문 줄 번호 (답 줄의 replyTo로 알게 됨)
  error?: ErrorKind;
};

// 맥락 카드를 아직 서버에 붙이지 않았을 때 (분석 번호만 받고 들어와 첫 질문을 기다림)
export type PendingCard = { analysisId: number; context?: ChatContext };

function toErrorKind(e: unknown): ErrorKind {
  if (e instanceof ApiError) {
    if (e.status === 429) return 'tooMany';
    if (e.status === 403) return { message: e.message };
  }
  return 'general';
}

// 분석이 지워짐 (명세서 0장 404). 맥락 카드는 불러오기 실패로 보이고 대화는 그대로 (설계 메모 3-6 항목)
const isGone = (e: unknown) => e instanceof ApiError && e.status === 404;

const sameCard = (m: Message, c: PendingCard) =>
  m.contextCard?.analysisId === c.analysisId &&
  m.contextCard.context?.type === c.context?.type &&
  m.contextCard.context?.id === c.context?.id;

export function useChat(params: ChatParams) {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState<Pending[]>([]);
  const [loading, setLoading] = useState(true);
  const [todayFailed, setTodayFailed] = useState(false);
  const [hasHistory, setHasHistory] = useState<boolean | null>(null);
  const [safetyUntil, setSafetyUntil] = useState<number | null>(null);
  const [pendingCard, setPendingCard] = useState<PendingCard | null>(null);
  // 질문 줄 번호 → 원문 (1층이 잡아 서버에 원문이 없는 질문을 이 창에서는 그대로 보여 주고 다시 보낼 때 씀)
  const [texts, setTexts] = useState<Record<number, string>>({});
  // [지금은 증상이 없어요]를 누른 긴급 답 줄 번호 (안내 글을 붙이고 칩을 끔)
  const [relieved, setRelieved] = useState<number[]>([]);
  // 다시 보낸 질문 줄 번호: 이 창에서는 사용자 말풍선을 새로 만들지 않음 (설계 메모 4-6 항목, 다시 열면 보임 #117)
  const [hidden, setHidden] = useState<number[]>([]);
  const sessionRef = useRef<number | null>(null);
  const pendingRef = useRef<Pending[]>([]);
  pendingRef.current = pending;
  const cardRef = useRef<PendingCard | null>(null);

  const setSession = (id: number | null) => {
    sessionRef.current = id;
    setSessionId(id);
  };

  const patch = (crid: string, p: Partial<Pending>) =>
    setPending((list) => list.map((q) => (q.crid === crid ? { ...q, ...p } : q)));

  // H-2를 불러 화면을 맞춤. 기다리던 답이 done이면 그 질문은 서버 목록으로 넘김
  const refresh = useCallback(async () => {
    const sid = sessionRef.current;
    if (sid === null) return;
    const list = await getMessages(sid);
    setMessages(list);
    const byId = new Map(list.map((m) => [m.id, m]));
    const now = Date.now();
    const learned: Record<number, string> = {};
    const hide: number[] = [];
    for (const q of pendingRef.current) {
      const qid = q.answerId !== undefined ? byId.get(q.answerId)?.replyTo : undefined;
      if (qid === undefined) continue;
      learned[qid] = q.content;
      if (q.dismissed) hide.push(qid);
    }
    setTexts((t) => ({ ...t, ...learned }));
    if (hide.length) setHidden((h) => [...h, ...hide]);
    setPending((cur) =>
      cur.flatMap((q) => {
        if (q.answerId === undefined || q.error) return [q];
        const a = byId.get(q.answerId);
        if (a?.status === 'done') return [];
        if (!a || now - q.sentAt > TIMEOUT_MS) return [{ ...q, error: 'general' as ErrorKind }];
        return [{ ...q, questionId: a.replyTo }];
      }),
    );
    for (const a of list) {
      if (a.answerType === 'crisis' && a.status === 'done') {
        setSafetyUntil((u) => Math.max(u ?? 0, nextKstMidnight())); // 서버도 같은 시각을 기록 (명세서 H-8)
      }
    }
  }, []);

  // 열 때: H-8 → H-2. 분석에서 들어왔으면 맥락 카드 (1단계 하루 한 대화, 설계 메모 3-4 항목)
  const open = useCallback(async () => {
    setLoading(true);
    setTodayFailed(false);
    const card = params.analysisId !== undefined ? { analysisId: params.analysisId, context: params.context } : null;
    try {
      const today = await findToday();
      setHasHistory(today.hasHistory);
      if (today.safetyModeUntil) setSafetyUntil(Date.parse(today.safetyModeUntil));
      let sid = today.sessionId;
      setSession(sid); // 아래 단계가 실패해도 첫 질문 때 오늘 대화를 또 만들지 않게
      let list: Message[] = [];
      if (sid !== null) list = await getMessages(sid);
      if (card && !list.some((m) => sameCard(m, card))) {
        if (sid === null && card.context) {
          sid = (await startSession(newRequestId(), card.analysisId, card.context)).sessionId;
          setSession(sid); // H-7이 실패해도 첫 질문 때 대화를 또 만들지 않게
        }
        if (sid !== null) {
          try {
            await addContext(sid, card.analysisId, newRequestId(), card.context);
            list = await getMessages(sid);
          } catch (e) {
            if (!isGone(e)) throw e;
            setPendingCard(card); // 카드만 보이고(불러오기 실패), 다시 붙이지 않음
          }
        } else {
          cardRef.current = card; // 분석 번호만: 대화는 첫 질문 때 만듦 (설계 메모 3-5 항목)
          setPendingCard(card);
        }
      }
      setSession(sid);
      setMessages(list);
    } catch {
      setTodayFailed(true); // 빈 새 대화 화면으로 열고 위에 [다시 불러오기] (설계 메모 3-6 항목)
      if (card) {
        cardRef.current = card;
        setPendingCard(card);
      }
    } finally {
      setLoading(false);
    }
  }, [params.analysisId, params.context]);

  useEffect(() => {
    void open();
  }, [open]);

  // 기다리는 답이 있으면 2초마다
  const waiting = pending.some((q) => q.answerId !== undefined && !q.error) || messages.some((m) => m.status === 'generating');
  useEffect(() => {
    if (!waiting) return;
    const t = setInterval(() => void refresh().catch(() => undefined), POLL_MS);
    return () => clearInterval(t);
  }, [waiting, refresh]);

  // 한 질문 보내기. 실패한 단계부터 같은 clientRequestId로 이어서 (설계 메모 3-5 항목)
  const deliver = useCallback(
    async (q: Pending) => {
      try {
        let sid = sessionRef.current;
        const card = cardRef.current;
        if (sid === null) {
          sid = (await startSession(q.crid, card?.analysisId, card?.context)).sessionId;
          setSession(sid);
        }
        if (card) {
          // 카드 줄과 질문 줄은 같은 표라 요청 번호를 나눔 (같으면 서버가 카드 줄을 질문으로 봄)
          try {
            await addContext(sid, card.analysisId, `${q.crid}-card`, card.context);
          } catch (e) {
            if (!isGone(e)) throw e; // 분석이 지워졌으면 카드 없이 질문은 그대로 보냄
          }
          cardRef.current = null;
        }
        setPendingCard(null); // 붙은 카드는 서버 목록으로 보이고, 지워진 분석의 카드는 첫 질문 뒤 치움
        let answerId: number;
        try {
          answerId = await sendQuestion(sid, q.content, q.crid, q.dismissed);
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) setSession(null); // 대화가 지워짐: 다시 시도 때 새로 만듦
          throw e;
        }
        patch(q.crid, { answerId });
        pendingRef.current = pendingRef.current.map((p) => (p.crid === q.crid ? { ...p, answerId } : p));
        await refresh();
      } catch (e) {
        patch(q.crid, { error: toErrorKind(e) });
      }
    },
    [refresh],
  );

  const ask = useCallback(
    (content: string, dismissed = false) => {
      const q: Pending = { crid: newRequestId(), content, dismissed, sentAt: Date.now() };
      setPending((list) => [...list, q]);
      void deliver(q);
    },
    [deliver],
  );

  const retry = useCallback(
    (crid: string) => {
      const q = pendingRef.current.find((p) => p.crid === crid);
      if (!q) return;
      const again = { ...q, error: undefined, answerId: undefined, sentAt: Date.now() };
      patch(crid, { error: undefined, answerId: undefined, sentAt: again.sentAt });
      void deliver(again);
    },
    [deliver],
  );

  // E4 [지금은 증상이 없어요]: 안내 글을 붙이고 같은 질문을 새 요청으로 다시 보냄 (설계 메모 4-6 항목)
  const dismiss = useCallback(
    (answer: Message) => {
      const text = answer.replyTo !== undefined ? texts[answer.replyTo] : undefined;
      if (!text) return;
      setRelieved((r) => [...r, answer.id]);
      ask(text, true);
    },
    [texts, ask],
  );

  return {
    sessionId,
    messages,
    pending,
    loading,
    todayFailed,
    hasHistory,
    safetyMode: safetyUntil !== null && safetyUntil > Date.now(),
    pendingCard,
    texts,
    relieved,
    hidden,
    busy: waiting || pending.some((q) => q.answerId === undefined && !q.error),
    open,
    ask,
    retry,
    dismiss,
  };
}

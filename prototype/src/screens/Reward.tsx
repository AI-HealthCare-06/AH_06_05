import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { getDrug } from '../dur';
import { diseasesFor, recommendations } from '../scenario';
import { useApp } from '../store';
import { C, R, T } from '../theme';
import { Btn, Card, Chip, Note, Screen } from '../ui';

const PER_GOAL = 10;
const BONUS = 10;

function useRecs() {
  const { s } = useApp();
  const drugs = s.items.filter((i) => i.edi && i.status !== 'excluded').map((i) => getDrug(i.edi!)!);
  return recommendations(diseasesFor(s.rxs.flatMap((r) => r.diseases)), drugs);
}

// RW-02 실천 목표 선택 (RW-01은 제외 확정 — RG-05에서 바로 옴)
export function Goals() {
  const { s, set, toTab } = useApp();
  const recs = useRecs();
  const [sel, setSel] = useState<string[]>(s.goals.map((g) => g.id));
  const full = sel.length >= 3;
  const toggle = (id: string) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : full ? sel : [...sel, id]);
  return (
    <Screen id="RW-02" title="실천 목표 선택" agendaKey="goals"
      footer={<View style={{ gap: 4 }}>
        <Btn label={`선택한 ${sel.length}개 목표로 시작하기`} disabled={!sel.length}
          onPress={() => { set({ goals: recs.filter((r) => sel.includes(r.id)).map((r) => ({ ...r, value: 0, done: false })), points: { ...s.points, today: 0 } }); toTab('today'); }} />
        {!sel.length && <Text style={[T.caption, { textAlign: 'center' }]}>0개면 누를 수 없어요</Text>}
      </View>}>
      <Text style={[T.body, { color: C.text2 }]}>이번 주에 실천할 목표를 골라 보세요. (최대 3개)</Text>
      <Text style={[T.bodyM, { color: C.p700, marginTop: 8 }]}>{sel.length}개 선택됨</Text>
      <View style={{ gap: 10, marginTop: 12 }}>
        {recs.map((r) => {
          const on = sel.includes(r.id);
          return (
            <Pressable key={r.id} onPress={() => toggle(r.id)} style={{ backgroundColor: C.card, borderRadius: R.card, borderWidth: 1.5, borderColor: on ? C.p600 : C.border, padding: 16, flexDirection: 'row', gap: 12, alignItems: 'center', opacity: !on && full ? 0.5 : 1 }}>
              <View style={{ width: 24, height: 24, borderRadius: 6, borderWidth: 1.5, borderColor: on ? C.p600 : C.borderStrong, backgroundColor: on ? C.p600 : C.card, alignItems: 'center', justifyContent: 'center' }}>{on && <Text style={{ color: '#fff', fontWeight: '800' }}>✓</Text>}</View>
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={T.bodyM}>{r.title}</Text>
                <Chip label={r.reason} tone="info" />
                <Text style={T.caption}>{r.desc}</Text>
              </View>
            </Pressable>
          );
        })}
      </View>
      {full && <Text style={[T.caption, { marginTop: 12 }]}>※ 3개를 모두 골랐어요. 바꾸려면 하나를 먼저 빼 주세요.</Text>}
      <Note>추천 {recs.length}개는 질환 · 먹는 약 기준이에요. "물 6잔" 같은 일반 목표는 넣지 않았어요 (심부전 · 신장병 수분 제한).</Note>
    </Screen>
  );
}

// RW-03 미실천 · RW-04 일부 완료 · RW-05 전체 완료 · RW-03-E1 저장 실패 · RW-03-E2 목표 없음
export function Today() {
  const { s, set, go } = useApp();
  const [err, setErr] = useState(false);
  const g = s.goals;
  if (!g.length) {
    return (
      <Screen id="RW-03-E2" title="오늘의 실천" agendaKey="today" back={false}>
        <Card style={{ alignItems: 'center', gap: 10, marginTop: 40 }}>
          <Text style={{ fontSize: 30, color: C.text2 }}>?</Text>
          <Text style={T.heading}>아직 실천 목표가 없어요</Text>
          <Text style={[T.caption, { textAlign: 'center' }]}>처방전을 분석하면 내 질환과 먹는 약에 맞는 목표를 추천해 드려요.</Text>
          <Btn label={s.analysis ? '실천 목표 선택하기' : '처방전 분석하기'} onPress={() => go(s.analysis ? 'goals' : 'capture')} style={{ alignSelf: 'stretch' }} />
        </Card>
      </Screen>
    );
  }
  const done = g.filter((x) => x.done).length;
  const pct = Math.round((done / g.length) * 100);
  const all = done === g.length;
  const id = err ? 'RW-03-E1' : done === 0 ? 'RW-03' : all ? 'RW-05' : 'RW-04';

  const record = (gid: string, value?: number) => {
    set((st) => {
      const goals = st.goals.map((x) => {
        if (x.id !== gid || x.done) return x; // 같은 날 다시 완료하면 무시 (P-4)
        const v = value ?? x.value;
        return { ...x, value: v, done: x.type === 'check' ? true : v >= (x.target || 0) };
      });
      const newly = goals.filter((x) => x.done).length - st.goals.filter((x) => x.done).length;
      const bonus = goals.every((x) => x.done) && !st.goals.every((x) => x.done) ? BONUS : 0;
      const add = newly * PER_GOAL + bonus;
      return { goals, points: { today: st.points.today + add, week: st.points.week + add, total: st.points.total + add }, streak: bonus ? st.streak + 1 : st.streak };
    });
  };

  if (all && !err) {
    return (
      <Screen id="RW-05" title="오늘의 실천" agendaKey="today" back={false}>
        <Card tone="success" style={{ alignItems: 'center', gap: 10, marginTop: 24 }}>
          <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: C.success, alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: '#fff', fontSize: 30, fontWeight: '800' }}>✓</Text></View>
          <Text style={T.caption}>오늘 {done} / {g.length}개 완료 · 100%</Text>
          <Text style={T.heading}>오늘 목표를 모두 완료했어요</Text>
          <Text style={[T.title, { color: C.success }]}>+{s.points.today}P 획득</Text>
          <Text style={T.bodyM}>연속 실천 {s.streak}일째</Text>
        </Card>
        <Btn label="달성 현황 보기" onPress={() => go('weekly')} style={{ marginTop: 16 }} />
        <Note>같은 날 다시 들어와도 포인트는 다시 주지 않아요. Figma는 전체 완료 +30P로 적혀 있는데, 목표당 10P + 보너스 10P로 계산하면 3개일 때 40P예요 — 기준 확인 필요.</Note>
      </Screen>
    );
  }

  return (
    <Screen id={id} title="오늘의 실천" agendaKey="today" back={false}>
      {err && (
        <Card tone="danger" style={{ gap: 8, marginBottom: 12 }}>
          <Text style={[T.body, { color: C.text }]}>기록하지 못했어요. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.</Text>
          <Btn label="다시 시도" kind="danger" onPress={() => setErr(false)} />
        </Card>
      )}
      <Card style={{ gap: 8 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={T.heading}>오늘 {done} / {g.length}개 완료</Text><Text style={[T.heading, { color: C.p700 }]}>{pct}%</Text>
        </View>
        <View style={{ height: 10, backgroundColor: C.muted, borderRadius: 5, overflow: 'hidden' }}><View style={{ width: `${pct}%`, height: 10, backgroundColor: C.p600 }} /></View>
      </Card>
      <View style={{ gap: 12, marginTop: 12 }}>
        {g.map((x) => (
          <Card key={x.id} tone={x.done ? 'success' : undefined} style={{ gap: 6 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <Text style={[T.bodyM, { flex: 1 }]}>{x.title.replace(' 30분', '')}</Text>
              {x.done && <Chip label="완료" tone="success" />}
            </View>
            <Chip label={x.reason} tone="info" />
            {x.type === 'check' ? (
              <>
                <Text style={T.caption}>{x.desc}</Text>
                {!x.done && <Btn label="실천 완료" kind="secondary" onPress={() => record(x.id)} />}
              </>
            ) : (
              <>
                <Text style={T.caption}>목표 {x.target}{x.unit} · 현재 {x.value}{x.unit} (10분씩 기록)</Text>
                {!x.done && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
                    <Pressable onPress={() => set((st) => ({ goals: st.goals.map((y) => (y.id === x.id ? { ...y, value: Math.max(0, y.value - 10) } : y)) }))} style={{ width: 44, height: 44, borderRadius: 22, borderWidth: 1, borderColor: C.borderStrong, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 22 }}>−</Text></Pressable>
                    <Text style={T.heading}>{x.value}분</Text>
                    <Pressable onPress={() => record(x.id, x.value + 10)} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: C.p600, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 22, color: '#fff' }}>+</Text></Pressable>
                  </View>
                )}
              </>
            )}
          </Card>
        ))}
      </View>
      <Text style={[T.bodyM, { textAlign: 'center', marginTop: 16, color: C.p700 }]}>
        {done === 0 ? `오늘 모든 목표를 완료하면 +${g.length * PER_GOAL + BONUS}P` : `현재 획득 ${s.points.today}P · 오늘 모두 완료하면 +${BONUS}P 추가`}
      </Text>
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 16 }}>
        <Btn label="달성 현황 보기" kind="secondary" onPress={() => go('weekly')} style={{ flex: 1 }} />
        <Btn label="(프로토타입) 저장 실패" kind="ghost" onPress={() => setErr(true)} style={{ flex: 1 }} />
      </View>
      <Note>Figma는 RW-03 · 04 · 05 프레임 3개, 여기서는 한 화면에서 상태만 바뀌어요 (안건 #24). 완료 취소는 막혀 있어요 (안건 #27).</Note>
    </Screen>
  );
}

// RW-06 이번 주 달성 현황 · RW-06-E1 기록 없음
export function Weekly() {
  const { s, toTab } = useApp();
  const days = ['월', '화', '수', '목', '금', '토', '일'];
  if (!s.goals.length) {
    return (
      <Screen id="RW-06-E1" title="달성 현황" agendaKey="weekly">
        <Card style={{ alignItems: 'center', gap: 10, marginTop: 40 }}>
          <Text style={{ fontSize: 30, color: C.text2 }}>?</Text>
          <Text style={T.heading}>아직 실천 기록이 없어요</Text>
          <Text style={T.caption}>오늘의 목표부터 시작해 보세요.</Text>
          <Btn label="오늘의 실천으로 이동" onPress={() => toTab('today')} style={{ alignSelf: 'stretch' }} />
        </Card>
      </Screen>
    );
  }
  const todayDone = s.goals.every((g) => g.done);
  const doneDays = [todayDone, false, false, false, false, false, false]; // 오늘 = 월요일
  const prev = 3; // 지난주에서 이어진 연속일은 예시
  const n = doneDays.filter(Boolean).length;
  return (
    <Screen id="RW-06" title="이번 주 달성 현황" agendaKey="weekly" footer={<Btn label="오늘의 실천으로 돌아가기" kind="secondary" onPress={() => toTab('today')} />}>
      <Card>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          {days.map((d, i) => (
            <View key={d} style={{ alignItems: 'center', gap: 6 }}>
              <Text style={T.small}>{d}</Text>
              <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: doneDays[i] ? C.p600 : C.muted, alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: doneDays[i] ? '#fff' : C.text3, fontWeight: '700' }}>{doneDays[i] ? '✓' : '–'}</Text></View>
            </View>
          ))}
        </View>
      </Card>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 12 }}>
        {[['이번 주', `${n} / 7일`], ['달성률', `${Math.round((n / 7) * 100)}%`], ['연속 실천', `${todayDone ? s.streak : prev - 1}일`], ['이번 주 포인트', `${s.points.today}P`], ['누적 포인트', `${s.points.total}P`]].map(([a, b]) => (
          <Card key={a} style={{ width: '47%', gap: 4 }}><Text style={T.small}>{a}</Text><Text style={T.title}>{b}</Text></Card>
        ))}
      </View>
      <Note>오늘(9/29)이 월요일이라 이번 주 기록은 오늘 하루예요. 누적 포인트 · 연속일의 과거 값은 예시예요.</Note>
    </Screen>
  );
}

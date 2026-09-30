import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { TODAY, useApp } from '../store';
import { C, T } from '../theme';
import { Btn, Card, Chip, Confirm, Disclaimer, Screen, Section } from '../ui';

const link = { color: C.p700, fontWeight: '600' as const, fontSize: 15 };

// CM-03 홈 · CM-03-E1 홈 첫 사용
export default function Home() {
  const { s, go, toTab } = useApp();
  const first = !s.analysis || s.analysisDeleted;
  const done = s.goals.filter((g) => g.done).length;
  const pending = s.items.filter((i) => i.status === 'excluded').length;
  const n = s.analysis?.warnings.length || 0;

  if (first) {
    return (
      <Screen id="CM-03-E1" title="홈" agendaKey="home" back={false}
        footer={<Btn label="첫 처방전 분석하기" onPress={() => go('capture')} />}>
        <Text style={T.title}>{s.user.name}님, 반가워요</Text>
        <Section title="처방전을 찍으면 이렇게 도와드려요">
          <Card style={{ gap: 12 }}>
            {['처방전 · 약봉투 사진 찍기', '약 이름이 맞는지 확인하기', '같이 먹으면 안 되는 약 점검', '복약 안내 · 생활습관 가이드 받기'].map((t, i) => (
              <View key={t} style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
                <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: C.p50, alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: C.p700, fontWeight: '800' }}>{i + 1}</Text></View>
                <Text style={T.body}>{t}</Text>
              </View>
            ))}
          </Card>
        </Section>
        <Section title="오늘의 실천" right={<Chip label="목표 없음" tone="neutral" />}>
          <Card><Text style={T.caption}>처방전을 분석하면 나에게 맞는 목표가 생겨요</Text></Card>
        </Section>
        <Section title="최근 분석" right={<Chip label="기록 없음" tone="neutral" />}>
          <Card><Text style={T.caption}>아직 분석한 기록이 없어요</Text></Card>
        </Section>
        <Section title="궁금한 점 물어보기">
          <Card onPress={() => toTab('chat')}><Text style={T.body}>약에 대한 일반 질문은 지금도 할 수 있어요 ›</Text></Card>
        </Section>
        <Disclaimer />
      </Screen>
    );
  }

  return (
    <Screen id="CM-03" title="홈" agendaKey="home" back={false}
      footer={<Btn label="처방전 · 약봉투 분석하기" onPress={() => go('capture')} />}>
      <Text style={T.caption}>{TODAY.label}</Text>
      <Text style={T.title}>{s.user.name}님, 안녕하세요</Text>

      <Section title="오늘의 실천" right={s.goals.length ? <Text style={T.bodyM}>{done} / {s.goals.length} 완료</Text> : <Chip label="목표 없음" tone="neutral" />}>
        <Card onPress={() => toTab('today')} style={{ gap: 10 }}>
          {s.goals.length ? (
            <>
              {s.goals.map((g) => (
                <View key={g.id} style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                  <Text style={T.body}>{g.title}</Text>
                  <Chip label={g.done ? '완료' : '아직'} tone={g.done ? 'success' : 'neutral'} />
                </View>
              ))}
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <Text style={T.caption}>오늘 진행률</Text><Text style={T.bodyM}>{Math.round((done / s.goals.length) * 100)}%</Text>
              </View>
              <View style={{ height: 8, backgroundColor: C.muted, borderRadius: 4, overflow: 'hidden' }}><View style={{ width: `${(done / s.goals.length) * 100}%`, height: 8, backgroundColor: C.p600 }} /></View>
            </>
          ) : <Text style={T.caption}>분석 결과의 생활습관 탭에서 목표를 골라 보세요 ›</Text>}
        </Card>
      </Section>

      <Section title={`최근 분석 · ${TODAY.short}`}>
        <Card onPress={() => go('result')} style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <Text style={[T.bodyM, { flex: 1 }]}>{s.rxs.map((r) => r.hospital).join(' · ')} 처방전 · 약 {s.items.filter((i) => i.edi && i.status !== 'excluded').length}개</Text>
            {n ? <Chip label={`확인 필요 ${n}건`} tone="caution" /> : <Chip label="확인된 위험 없음" tone="success" />}
          </View>
          {pending > 0 && <Text style={T.caption}>점검에서 빠진 약 {pending}개</Text>}
          <Text style={link}>결과 보기 {'>'}</Text>
        </Card>
        <Pressable onPress={() => go('history')}><Text style={link}>지난 기록 전체 보기 {'>'}</Text></Pressable>
      </Section>

      <Section title="궁금한 점 물어보기">
        <Card onPress={() => toTab('chat')}><Text style={T.body}>"이 약은 밥 먹고 먹어야 하나요?"</Text></Card>
      </Section>
      <Disclaimer />
    </Screen>
  );
}

// CM-04 지난 기록 · CM-04-E1 삭제 확인 · CM-04-E2 기록 없음
export function History() {
  const { s, set, go } = useApp();
  const [del, setDel] = useState<string | null>(null);
  const [hidden, setHidden] = useState<string[]>([]);
  const rows = [
    ...(s.analysis && !s.analysisDeleted ? [{ id: 'now', date: '9월 29일 (월)', title: `${s.rxs.map((r) => r.hospital).join(' · ')} 처방전 · 약 ${s.items.filter((i) => i.edi && i.status !== 'excluded').length}개`, chip: s.analysis.warnings.length ? [`확인 필요 ${s.analysis.warnings.length}건`, 'caution'] : ['확인된 위험 없음', 'success'], sub: '고혈압 · 당뇨 · 고지혈증', action: '결과 보기 >', fail: false }] : []),
    { id: 'p1', date: '9월 2일 (화)', title: '△△의원 처방전 · 약 2개 (예시)', chip: ['확인된 위험 없음', 'success'], sub: '고지혈증', action: '결과 보기 >', fail: false },
    { id: 'p2', date: '8월 14일 (목)', title: '사진을 읽지 못했어요 (예시)', chip: ['분석 실패', 'danger'], sub: '원본 사진을 저장하지 않아 다시 찍어야 해요', action: '다시 분석하기 >', fail: true },
  ].filter((r) => !hidden.includes(r.id));

  return (
    <Screen id={rows.length ? (del ? 'CM-04-E1' : 'CM-04') : 'CM-04-E2'} title="지난 기록">
      {rows.length === 0 ? (
        <Card style={{ alignItems: 'center', gap: 10, marginTop: 40 }}>
          <Text style={{ fontSize: 32 }}>?</Text>
          <Text style={T.heading}>아직 분석한 기록이 없어요</Text>
          <Text style={T.caption}>처방전이나 약봉투를 찍어 첫 분석을 해 보세요.</Text>
          <Btn label="처방전 분석하기" onPress={() => go('capture')} style={{ alignSelf: 'stretch' }} />
        </Card>
      ) : (
        <>
          <Text style={[T.body, { color: C.text2 }]}>분석한 처방전과 안내문을 최근 순으로 모아 보여드려요.</Text>
          <View style={{ gap: 12, marginTop: 16 }}>
            {rows.map((r) => (
              <Card key={r.id} style={{ gap: 6 }}>
                <Text style={T.small}>{r.date}</Text>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
                  <Text style={[T.bodyM, { flex: 1 }]}>{r.title}</Text>
                  <Chip label={r.chip[0]} tone={r.chip[1] as any} />
                </View>
                <Text style={T.caption}>{r.sub}</Text>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 }}>
                  <Pressable onPress={() => (r.fail ? go('capture') : r.id === 'now' ? go('result') : null)}><Text style={link}>{r.action}</Text></Pressable>
                  <Pressable onPress={() => setDel(r.id)}><Text style={[T.caption, { color: C.danger }]}>삭제</Text></Pressable>
                </View>
              </Card>
            ))}
          </View>
        </>
      )}
      <Confirm visible={!!del} title="이 기록을 삭제할까요?" body="분석 결과와 복약 안내문이 모두 지워져요. 지운 기록은 되돌릴 수 없어요." ok="삭제하기"
        onCancel={() => setDel(null)} onOk={() => { if (del === 'now') set({ analysisDeleted: true }); else setHidden([...hidden, del!]); setDel(null); }} />
    </Screen>
  );
}

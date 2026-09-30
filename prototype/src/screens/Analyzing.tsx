import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { getDrug, shortName } from '../dur';
import { useApp } from '../store';
import { C, T } from '../theme';
import { Btn, Card, Chip, Note, Screen } from '../ui';

const STEPS = ['약 정보를 확인하고 있어요', '같이 먹으면 안 되는 약을 점검하고 있어요', '쉬운 말로 안내문을 쓰고 있어요'];
const STEPS_DONE = ['약 정보 확인', '같이 먹으면 안 되는 약 점검', '안내문 작성'];

// RG-01 분석 진행 중 · RG-01-E1 분석 실패
export default function Analyzing() {
  const { s, set, replace, toTab, go } = useApp();
  const [step, setStep] = useState(0);
  const [fail, setFail] = useState(false);
  const [run, setRun] = useState(0);
  useEffect(() => {
    setStep(0);
    const t = [setTimeout(() => setStep(1), 1000), setTimeout(() => setStep(2), 2000), setTimeout(() => setStep(3), 3200)];
    return () => t.forEach(clearTimeout);
  }, [run]);
  useEffect(() => {
    if (step === 3 && !fail) {
      set((st) => ({ analysis: st.analysis ? { ...st.analysis, status: 'done' } : st.analysis }));
      const t = setTimeout(() => replace('result'), 400);
      return () => clearTimeout(t);
    }
  }, [step, fail]);

  const checked = s.items.filter((i) => i.edi && i.status !== 'excluded');
  const out = s.items.filter((i) => i.status === 'excluded').length;

  if (fail && step >= 2) {
    return (
      <Screen id="RG-01-E1" title="분석 중" agendaKey="analyzing" back={false}
        footer={<View style={{ gap: 8 }}>
          <Btn label="다시 시도" onPress={() => { setFail(false); setRun(run + 1); }} />
          <Btn label="안전성 결과만 먼저 보기" kind="secondary" onPress={() => { set((st) => ({ analysis: st.analysis && { ...st.analysis, status: 'failed' } })); replace('result'); }} />
          <Btn label="홈으로" kind="ghost" onPress={() => toTab('home')} />
        </View>}>
        <Text style={T.title}>안내문을 만들지 못했어요</Text>
        <Text style={[T.body, { color: C.text2, marginTop: 4 }]}>잠시 문제가 생겼어요. 다시 시도해 주세요.</Text>
        <View style={{ gap: 10, marginTop: 20 }}>
          {STEPS_DONE.map((l, i) => (
            <Card key={l} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <Text style={T.bodyM}>{i + 1}  {l}</Text>
              <Chip label={i < 2 ? '완료' : '실패'} tone={i < 2 ? 'success' : 'danger'} />
            </Card>
          ))}
        </View>
        <Text style={[T.caption, { marginTop: 12 }]}>※ 안전성 점검은 끝났어요. 경고는 먼저 확인할 수 있어요.</Text>
      </Screen>
    );
  }

  return (
    <Screen id="RG-01" title="분석 중" agendaKey="analyzing" back={false}
      footer={<Btn label="홈에서 기다리기" kind="secondary" onPress={() => toTab('home')} />}>
      <Text style={T.title}>잠시만 기다려 주세요</Text>
      <Text style={[T.body, { color: C.text2, marginTop: 4 }]}>20 ~ 30초 정도 걸려요</Text>
      <View style={{ gap: 10, marginTop: 20 }}>
        {STEPS.map((l, i) => (
          <Card key={l} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 }}>
              {step === i ? <ActivityIndicator color={C.p600} /> : <Text style={{ fontSize: 16, width: 20, textAlign: 'center', fontWeight: '800', color: step > i ? C.success : C.text3 }}>{i + 1}</Text>}
              <Text style={[T.bodyM, { flex: 1 }]}>{l}</Text>
            </View>
            <Chip label={step > i ? '완료' : step === i ? '진행 중' : '대기'} tone={step > i ? 'success' : step === i ? 'info' : 'neutral'} />
          </Card>
        ))}
      </View>
      <Card style={{ marginTop: 16, gap: 4 }}>
        <Text style={T.label}>점검하는 약</Text>
        <Text style={T.caption}>약 {checked.length}개 점검 중{out ? ` · ${out}개는 찾지 못해 점검에서 빠짐` : ''}</Text>
        <Text style={T.body}>{checked.slice(0, 3).map((i) => shortName(getDrug(i.edi!)!.name).replace(/\d.*$/, '')).join(' · ')}{checked.length > 3 ? ` 외 ${checked.length - 3}개` : ''}</Text>
      </Card>
      <Text style={[T.caption, { marginTop: 12 }]}>※ 화면을 나가도 분석은 계속돼요. 끝나면 홈의 "최근 분석"에서 볼 수 있어요.</Text>
      <Pressable onPress={() => setFail(true)}><Text style={[T.small, { color: C.text3, marginTop: 14 }]}>(프로토타입) 안내문 작성 실패 보기 — RG-01-E1</Text></Pressable>
      <Note>R-1 분석 시작 → R-2 상태 조회 흉내. 안전성 점검은 AI 없이 DUR 데이터 조회로만 판정해요.</Note>
    </Screen>
  );
}

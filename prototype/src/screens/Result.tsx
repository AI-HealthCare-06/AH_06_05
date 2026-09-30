import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { CHECKED_ITEMS, DUR_SOURCE, Warning, categoryOf, cautionOf, getDrug, purposeOf, shortName } from '../dur';
import { LIFESTYLE_DISCLAIMER, conflictsFor, diseasesFor, medicationLinks } from '../scenario';
import { TODAY, useApp } from '../store';
import { C, R, T } from '../theme';
import { Btn, Card, Chip, Disclaimer, Note, Radio, Screen, Section } from '../ui';

const SEV: Record<string, [string, any]> = { danger: ['위험', 'danger'], caution: ['주의', 'caution'], info: ['참고', 'info'] };
type TabKey = 'safety' | 'med' | 'life';
const link = { color: C.p700, fontWeight: '600' as const, marginTop: 8 };

// "1일 2회 · 아침 · 저녁 식후" → "하루 2번, 아침 · 저녁 식후 1알"
const howTo = (timing: string, dose: string, days: number) => {
  const m = timing.match(/1일 (\d)회 · (.*)/);
  return `${m ? `하루 ${m[1]}번, ${m[2]}` : timing} ${dose}${days ? ` · ${days}일` : ''}`;
};

// RG-02 · RG-02-E1 · RG-04 · RG-05 · RG-05-E1 분석 결과
export default function Result({ tab: initTab }: { tab?: TabKey }) {
  const { s, go } = useApp();
  const [tab, setTab] = useState<TabKey>(initTab || 'safety');
  if (!s.analysis) return null;
  const ws = s.analysis.warnings;
  const dis = diseasesFor(s.rxs.flatMap((r) => r.diseases));
  const id = tab === 'safety' ? (ws.length ? 'RG-02' : 'RG-02-E1') : tab === 'med' ? 'RG-04' : dis.length ? 'RG-05' : 'RG-05-E1';
  const n = (k: string) => ws.filter((w) => w.severity === k).length;
  const cnt = s.items.filter((i) => i.edi && i.status !== 'excluded').length;
  const sev = [n('danger') && `위험 ${n('danger')}`, n('caution') && `주의 ${n('caution')}`, n('info') && `참고 ${n('info')}`].filter(Boolean).join(' · ');
  return (
    <Screen id={id} title="분석 결과" agendaKey={tab}
      footer={tab !== 'life' ? <View style={{ flexDirection: 'row', gap: 8 }}>
        <Btn label="챗봇에 물어보기" kind="secondary" onPress={() => go('chat')} style={{ flex: 1 }} />
        <Btn label="실천 시작하기" onPress={() => go('goals')} style={{ flex: 1 }} />
      </View> : undefined}>
      <Card style={{ gap: 4 }}>
        <Text style={T.caption}>{TODAY.short} 분석</Text>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={T.bodyM}>처방전 {s.rxs.length}장 · 약 {cnt}개</Text>
          {ws.length ? <Chip label={sev} tone={n('danger') ? 'danger' : 'caution'} /> : <Chip label="확인된 위험 없음" tone="success" />}
        </View>
        <Text style={T.caption}>{s.rxs.map((r) => r.hospital).join(' · ')}</Text>
      </Card>
      <View style={{ flexDirection: 'row', backgroundColor: C.muted, borderRadius: R.control, padding: 4, marginTop: 12 }}>
        {([['safety', '안전성'], ['med', '복약 안내'], ['life', '생활습관']] as [TabKey, string][]).map(([k, l]) => (
          <Pressable key={k} onPress={() => setTab(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 9, backgroundColor: tab === k ? C.card : 'transparent', alignItems: 'center' }}>
            <Text style={{ fontSize: 15, fontWeight: tab === k ? '700' : '500', color: tab === k ? C.p700 : C.text2 }}>{l}</Text>
          </Pressable>
        ))}
      </View>
      {tab === 'safety' ? <Safety /> : s.analysis.status === 'failed' ? <Failed /> : tab === 'med' ? <Med /> : <Life />}
      <Disclaimer />
    </Screen>
  );
}

function Failed() {
  const { go } = useApp();
  return (
    <Card style={{ marginTop: 12, gap: 8 }}>
      <Text style={T.subhead}>안내문을 만들지 못했어요</Text>
      <Text style={T.caption}>안전성 점검 결과는 먼저 볼 수 있어요. 다시 시도하면 안내문을 만들어 드려요 (REQ-056).</Text>
      <Btn label="다시 시도" onPress={() => go('analyzing')} />
    </Card>
  );
}

function Excluded() {
  const { s } = useApp();
  const ex = s.items.filter((i) => i.status === 'excluded');
  if (!ex.length) return null;
  return <Text style={[T.caption, { color: C.warning, marginTop: 12 }]}>※ {ex.map((e) => `"${e.raw}"`).join(', ')}은(는) 찾지 못해 점검에서 빠졌어요. 약사에게 확인해 주세요.</Text>;
}

function Safety() {
  const { s, go } = useApp();
  const ws = s.analysis!.warnings;
  const cnt = s.items.filter((i) => i.edi && i.status !== 'excluded').length;
  if (!ws.length) {
    return (
      <View style={{ marginTop: 12 }}>
        <Excluded />
        <Card tone="success" style={{ marginTop: 12 }}>
          <Text style={T.heading}>확인된 위험이 없어요</Text>
          <Text style={[T.caption, { color: C.text, marginTop: 6 }]}>점검한 약 {cnt}개에서 같이 먹으면 안 되는 조합을 찾지 못했어요.</Text>
        </Card>
        <Section title="이렇게 점검했어요">
          {[...CHECKED_ITEMS.filter((c) => c.type !== 'polypharmacy'), { type: 'dose', label: '하루 최대량 초과' }].map((c) => <Card key={c.type} style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={T.bodyM}>{c.label}</Text><Chip label="확인됨" tone="success" /></Card>)}
        </Section>
        <Text style={[T.caption, { marginTop: 12 }]}>※ 우리 자료에 없는 조합일 수도 있어요. 새 약이나 영양제를 드시기 전에는 약사와 상의하세요.</Text>
      </View>
    );
  }
  return (
    <View style={{ marginTop: 4 }}>
      <Excluded />
      <View style={{ gap: 12, marginTop: 12 }}>
        {ws.map((w) => <WarnCard key={w.id} w={w} onPress={() => go('warning', { id: w.id })} />)}
      </View>
      <Note>경고는 실제 DUR 데이터로 판정했어요 — {DUR_SOURCE}</Note>
    </View>
  );
}

function WarnCard({ w, onPress }: { w: Warning; onPress: () => void }) {
  const [l, tone] = SEV[w.severity];
  return (
    <Card tone={w.severity === 'danger' ? 'danger' : w.severity === 'caution' ? 'caution' : 'info'} onPress={onPress}>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}><Chip label={l} tone={tone} /><Text style={T.label}>{w.title}</Text></View>
      <Text style={[T.bodyM, { marginTop: 8 }]}>{w.drugs.length <= 2 ? w.drugs.map((d) => d.name).join(w.type === 'interaction' ? ' + ' : ' · ') : `${w.drugs.length}가지 약`}</Text>
      <Text style={[T.body, { marginTop: 4 }]}>{w.summary}</Text>
      <Text style={[T.caption, { marginTop: 6 }]}>근거 · {w.source}</Text>
      <Text style={link}>자세히 보기 {'>'}</Text>
    </Card>
  );
}

function Med() {
  const { s, go, set } = useApp();
  const [fb, setFb] = useState<null | 1 | -1>(null);
  const drugs = s.items.filter((i) => i.edi && i.status !== 'excluded');
  const ex = s.items.filter((i) => i.status === 'excluded');
  return (
    <View style={{ marginTop: 12, gap: 12 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Chip label="▶  음성으로 듣기" tone="primary" /><Text style={T.caption}>속도 1.0배 (선택 구현)</Text>
      </View>
      {drugs.map((i) => {
        const d = getDrug(i.edi!)!;
        return (
          <Card key={i.id} style={{ gap: 6 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
              <Text style={[T.subhead, { flex: 1 }]}>{shortName(d.name)}</Text><Chip label={categoryOf(d.cls)} tone="info" />
            </View>
            <Text style={T.body}><Text style={T.bodyM}>무엇에 쓰나요 · </Text>{purposeOf(d.cls)}</Text>
            <Text style={T.body}><Text style={T.bodyM}>어떻게 먹나요 · </Text>{howTo(i.timing, i.dose, i.days)}</Text>
            <Text style={T.body}><Text style={T.bodyM}>주의할 점 · </Text>{cautionOf(d.name, d.ingrName) || '(허가정보를 바탕으로 AI가 작성할 자리)'}</Text>
            <Text style={T.caption}>출처 · 식약처 의약품 허가정보</Text>
            <Pressable onPress={() => { set({ chatContext: { kind: 'drug', title: shortName(d.name) } }); go('chat'); }}><Text style={link}>이 약 물어보기 {'>'}</Text></Pressable>
          </Card>
        );
      })}
      {ex.map((i) => (
        <Card key={i.id} tone="caution" style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={T.subhead}>{i.raw}</Text><Chip label="찾지 못함" tone="danger" /></View>
          <Text style={T.caption}>자료에서 찾지 못해 안내를 만들 수 없어요. 약사에게 확인해 주세요.</Text>
        </Card>
      ))}
      <Card style={{ gap: 10 }}>
        <Text style={T.label}>이 안내가 도움이 됐나요?</Text>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Btn label={fb === 1 ? '✓ 도움됐어요' : '도움됐어요'} kind={fb === 1 ? 'primary' : 'secondary'} onPress={() => setFb(1)} style={{ flex: 1 }} />
          <Btn label={fb === -1 ? '✓ 도움 안 됐어요' : '도움 안 됐어요'} kind={fb === -1 ? 'primary' : 'secondary'} onPress={() => setFb(-1)} style={{ flex: 1 }} />
        </View>
        <Text style={[T.caption, { color: C.p700 }]}>의견 남기기 {'>'}</Text>
      </Card>
      <Note>"무엇에 쓰나요"는 약 분류 코드, "주의할 점"은 예시 문구예요. 실제 서비스는 허가정보를 근거로 AI가 작성해요.</Note>
    </View>
  );
}

function Life() {
  const { s, set, go } = useApp();
  const [pick, setPick] = useState<string | null>(null);
  const codes = s.rxs.flatMap((r) => r.diseases);
  const dis = diseasesFor(codes);
  const drugs = s.items.filter((i) => i.edi && i.status !== 'excluded').map((i) => getDrug(i.edi!)!);
  const links = medicationLinks(drugs, dis.length ? dis : diseasesFor(['I10', 'E11', 'E78']));
  const conflicts = conflictsFor(dis);
  const LinkList = () => (
    <Card style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}><Chip label="약과 함께" tone="info" /><Text style={T.label}>드시는 약 때문에 조심할 것</Text></View>
      {links.map((l, k) => (
        <View key={k} style={{ gap: 2 }}>
          <Text style={T.body}><Text style={T.bodyM}>{l.drug.replace(/\d.*$/, '')}</Text> · {l.advice}</Text>
          {l.requiresClinician && <Chip label="의료진 확인 · 실천 목표로 만들지 않음" tone="caution" />}
        </View>
      ))}
    </Card>
  );
  if (!dis.length) {
    return (
      <View style={{ marginTop: 12, gap: 12 }}>
        <Card tone="caution" style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={T.subhead}>질환 정보를 찾지 못했어요</Text><Chip label="확인 필요" tone="caution" /></View>
          <Text style={T.caption}>약봉투에는 질병분류기호가 없어서 어떤 질환인지 알 수 없어요.</Text>
        </Card>
        {links.length > 0 && <LinkList />}
        <Card>
          <Text style={T.label}>해당하는 질환이 있으면 골라 주세요 (선택)</Text>
          {[['I10', '고혈압'], ['E11', '당뇨병'], ['E78', '고지혈증'], ['none', '해당 없음 · 모르겠어요']].map(([c, l]) => <Radio key={c} on={pick === c} label={l} onPress={() => setPick(c)} />)}
          <Btn label="선택한 질환으로 다시 보기" disabled={!pick || pick === 'none'} onPress={() => set((st) => ({ rxs: st.rxs.map((r, i) => (i === 0 ? { ...r, diseases: [pick!] } : r)) }))} style={{ marginTop: 8 }} />
        </Card>
      </View>
    );
  }
  return (
    <View style={{ marginTop: 12, gap: 12 }}>
      <Card style={{ gap: 4 }}>
        <Text style={T.small}>확인한 질환</Text>
        <Text style={T.subhead}>{dis.map((d) => d.name).join(' · ')}</Text>
        <Text style={T.caption}>처방전의 질병분류기호로 확인했어요 ({codes.join(', ')})</Text>
      </Card>
      {conflicts.map((c) => (
        <Card key={c.condition} tone="caution"><Chip label="의료진 상담 필요" tone="caution" /><Text style={[T.caption, { color: C.text, marginTop: 6 }]}>{c.rule}</Text></Card>
      ))}
      {links.length > 0 && <LinkList />}
      {dis.map((d) => (
        <Card key={d.id} style={{ gap: 6 }}>
          <Text style={T.subhead}>{d.name}</Text>
          {d.lifestyle.slice(0, 2).map((l) => <Text key={l.category} style={T.body}>· {l.category} — {l.goal}</Text>)}
        </Card>
      ))}
      <Text style={T.caption}>출처 · {Array.from(new Set(dis.flatMap((d) => d.lifestyle.slice(0, 2).map((l) => l.source)))).join(' · ')}</Text>
      <Text style={[T.small, { color: C.text3 }]}>문서명 · 발행일 · URL은 아직 채우기 전이에요 (안건 #30)</Text>
      <Btn label="이 목표로 실천 시작하기" onPress={() => go('goals')} style={{ marginTop: 8 }} />
      <Text style={T.caption}>{LIFESTYLE_DISCLAIMER}</Text>
    </View>
  );
}

// RG-03 경고 자세히 보기
export function WarningDetail({ id }: { id: string }) {
  const { s, go, set } = useApp();
  const w = s.analysis?.warnings.find((x) => x.id === id);
  if (!w) return null;
  const [l, tone] = SEV[w.severity];
  return (
    <Screen id="RG-03" title="경고 자세히 보기" agendaKey="warning"
      footer={<Btn label="이 경고 챗봇에 물어보기" onPress={() => { set({ chatContext: { kind: 'warning', title: w.drugs.map((d) => d.name).join(' + '), text: w.summary, source: w.source } }); go('chat'); }} />}>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}><Chip label={l} tone={tone} /><Text style={T.heading}>{w.title}</Text></View>
      <Text style={[T.body, { marginTop: 10 }]}>{w.drugs.length}가지 약을 같이 드시고 있어요.</Text>
      <View style={{ gap: 10, marginTop: 12 }}>
        {w.drugs.map((d) => {
          const g = getDrug(d.edi);
          return <Card key={d.edi}><Text style={T.bodyM}>{d.name}</Text><Text style={T.caption}>{d.hospital || ''}{g ? ` · ${categoryOf(g.cls)} · 성분 ${g.ingrName.split(/\s{2,}/)[0]}` : ''}</Text></Card>;
        })}
      </View>
      <Section title="왜 조심해야 하나요">
        <Card><Text style={T.body}>{w.summary}</Text><Text style={[T.caption, { marginTop: 8 }]}>원문 · {w.reason}</Text></Card>
      </Section>
      <Section title="근거와 출처">
        <Card style={{ gap: 6 }}>
          <Text style={T.body}>{w.source}{w.noticeDate ? ` (고시일 ${w.noticeDate})` : ''}</Text>
          <Text style={T.caption}>판정 방식 · 식약처 DUR 데이터 조회 (AI가 판단하지 않음)</Text>
        </Card>
      </Section>
      <Text style={[T.caption, { marginTop: 16 }]}>※ 약을 임의로 끊지 말고, 처방한 의사나 약사와 먼저 상의하세요.</Text>
      <Disclaimer />
    </Screen>
  );
}

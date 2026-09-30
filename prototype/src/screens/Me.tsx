import React, { useState } from 'react';
import { Pressable, ScrollView, Switch, Text, View } from 'react-native';
import { useApp } from '../store';
import { C, R, T } from '../theme';
import { Btn, Card, Check, Confirm, Field, Note, Radio, Screen, Section } from '../ui';

function Row({ label, onPress, danger }: { label: string; onPress?: () => void; danger?: boolean }) {
  return (
    <Pressable onPress={onPress} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: C.border }}>
      <Text style={[T.body, danger && { color: C.danger }]}>{label}</Text>
      {!danger && <Text style={[T.body, { color: C.text3 }]}>{'>'}</Text>}
    </Pressable>
  );
}

// CM-05 내정보
export default function Me() {
  const { s, set, go, resetAll } = useApp();
  const [out, setOut] = useState(false);
  return (
    <Screen id="CM-05" title="내정보" agendaKey="me" back={false}>
      <Card style={{ gap: 4 }}>
        <Text style={T.heading}>{s.user.name}님</Text>
        <Text style={T.caption}>{s.user.birthYear}년생 · {s.user.sex === 'M' ? '남성' : '여성'}</Text>
        <Text style={T.caption}>{s.user.email}</Text>
        <Pressable onPress={() => go('editProfile')}><Text style={{ color: C.p700, fontWeight: '600', marginTop: 6 }}>정보 수정 {'>'}</Text></Pressable>
      </Card>
      <Card style={{ marginTop: 16, paddingVertical: 0 }}>
        <Row label="지난 기록" onPress={() => go('history')} />
        <Row label="민감정보 동의 내역" onPress={() => go('consents')} />
        <Row label="대화 보관 · 삭제" onPress={() => go('retention')} />
        <Row label="개인정보 처리방침" />
        <Row label="서비스 안내 · 면책 고지" />
      </Card>
      <Card style={{ marginTop: 16, paddingVertical: 0 }}>
        <Row label="로그아웃" danger onPress={() => setOut(true)} />
        <Row label="회원 탈퇴" danger onPress={() => go('withdraw')} />
      </Card>
      <Text style={[T.caption, { textAlign: 'center', marginTop: 12 }]}>버전 0.1.0</Text>

      <Section title="회의용 설정">
        <Card style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={T.bodyM}>화면 ID 표시</Text>
          <Switch value={s.showIds} onValueChange={(v) => set({ showIds: v })} />
        </Card>
      </Section>
      <Confirm visible={out} title="로그아웃할까요?" body="다시 로그인하면 이어서 쓸 수 있어요." ok="로그아웃" danger={false} onCancel={() => setOut(false)} onOk={() => { setOut(false); set({ loggedIn: false }); }} />
      <Note>로그아웃해도 이 기기의 체험 데이터는 남아 있어요. 처음부터 보려면 회원 탈퇴를 하세요.</Note>
      <Pressable onPress={resetAll}><Text style={[T.small, { color: C.text3, textAlign: 'center', marginTop: 10 }]}>(프로토타입) 처음부터 다시</Text></Pressable>
    </Screen>
  );
}

// CM-06 내 정보 수정
export function EditProfile() {
  const { s, set, back } = useApp();
  const [name, setName] = useState(s.user.name);
  const [year, setYear] = useState(s.user.birthYear);
  const [sex, setSex] = useState(s.user.sex);
  const [open, setOpen] = useState(false);
  return (
    <Screen id="CM-06" title="내 정보 수정" agendaKey="me" footer={<Btn label="저장하기" onPress={() => { set({ user: { ...s.user, name, birthYear: year, sex } }); back(); }} />}>
      <View style={{ gap: 18 }}>
        <Field label="이메일" value={s.user.email} editable={false} helper="이메일은 바꿀 수 없어요" />
        <Field label="이름 (별명) · 선택" value={name} onChangeText={setName} />
        <View style={{ gap: 6 }}>
          <Text style={T.label}>출생연도</Text>
          <Pressable onPress={() => setOpen(!open)} style={{ borderWidth: 1, borderColor: C.borderStrong, borderRadius: R.control, padding: 14, backgroundColor: C.card, flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={T.body}>{year}년</Text><Text style={T.body}>▼</Text>
          </Pressable>
          {open && (
            <ScrollView style={{ maxHeight: 220, borderWidth: 1, borderColor: C.border, borderRadius: R.control, backgroundColor: C.card }}>
              {Array.from({ length: 70 }, (_, i) => 1940 + i).map((y) => <Pressable key={y} onPress={() => { setYear(y); setOpen(false); }} style={{ padding: 12 }}><Text style={[T.body, y === year && { color: C.p700, fontWeight: '700' }]}>{y}년</Text></Pressable>)}
            </ScrollView>
          )}
        </View>
        <View>
          <Text style={T.label}>성별</Text>
          <View style={{ flexDirection: 'row' }}><Radio on={sex === 'M'} label="남성" onPress={() => setSex('M')} /><Radio on={sex === 'F'} label="여성" onPress={() => setSex('F')} /></View>
          <Text style={T.caption}>※ 출생연도 · 성별을 바꾸면 다음 분석부터 반영돼요. 지난 기록은 그대로예요.</Text>
        </View>
      </View>
    </Screen>
  );
}

// CM-07 회원 탈퇴
export function Withdraw() {
  const { resetAll, back } = useApp();
  const [ok, setOk] = useState(false);
  return (
    <Screen id="CM-07" title="회원 탈퇴" agendaKey="me"
      footer={<View style={{ gap: 8 }}><Btn label="탈퇴하기" kind="danger" disabled={!ok} onPress={resetAll} /><Btn label="취소" kind="secondary" onPress={back} /></View>}>
      <Text style={T.heading}>탈퇴하면 아래 정보가 바로 지워져요</Text>
      <Card style={{ marginTop: 16, gap: 6 }}>
        <Text style={T.label}>지워지는 정보</Text>
        {['처방전에서 읽어낸 진료 정보', '분석 결과와 복약 안내문', '실천 기록과 포인트', '챗봇 대화 내용'].map((t) => <Text key={t} style={T.body}>· {t}</Text>)}
        <Text style={[T.caption, { color: C.danger, marginTop: 6 }]}>※ 지운 정보는 되돌릴 수 없어요.</Text>
      </Card>
      <View style={{ marginTop: 12 }}><Check on={ok} label="위 내용을 확인했어요" onPress={() => setOk(!ok)} /></View>
    </Screen>
  );
}

// CM-05 민감정보 동의 내역
export function Consents() {
  return (
    <Screen id="CM-05" title="민감정보 동의 내역" agendaKey="me">
      {[['서비스 이용약관', '2026-09-29 동의'], ['개인정보 수집 · 이용', '2026-09-29 동의'], ['민감정보(진료기록) 수집 · 이용', '2026-09-29 동의']].map(([a, b]) => (
        <Card key={a} style={{ marginBottom: 12 }}><Text style={T.bodyM}>{a}</Text><Text style={T.caption}>{b}</Text></Card>
      ))}
      <Btn label="민감정보 동의 철회" kind="secondary" />
      <Note>철회하면 업로드 · 분석을 쓸 수 없고, 처방전 · 분석 · 안내문 · 챗봇 대화가 지워지는 안이에요 (안건 #6). 이 버튼은 동작하지 않아요.</Note>
    </Screen>
  );
}

// MY-S1 대화 보관 · 삭제 · MY-S1-E1 전체 삭제 확인
export function Retention() {
  const { s, set } = useApp();
  const [del, setDel] = useState(false);
  const d = s.retentionDays;
  return (
    <Screen id={del ? 'MY-S1-E1' : 'MY-S1'} title="대화 보관 · 삭제" agendaKey="me">
      <Text style={[T.body, { color: C.text2 }]}>챗봇 대화 기록을 얼마나 보관할지 정하고, 필요하면 한 번에 지울 수 있어요.</Text>
      <Section title="대화 보관 기간">
        <Card style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <Pressable onPress={() => set({ retentionDays: Math.max(30, d - 30) })} style={{ padding: 8 }}><Text style={{ fontSize: 24, color: C.p700 }}>−</Text></Pressable>
          <Text style={T.title}>{d}일</Text>
          <Pressable onPress={() => set({ retentionDays: Math.min(360, d + 30) })} style={{ padding: 8 }}><Text style={{ fontSize: 24, color: C.p700 }}>+</Text></Pressable>
        </Card>
        <Text style={T.caption}>30일 단위로 30일 ~ 360일까지 정할 수 있어요 (기본 180일). 기간이 지난 대화는 자동으로 삭제돼요.</Text>
      </Section>
      <Card tone="info" style={{ marginTop: 16, gap: 4 }}>
        <Text style={T.label}>알아 두세요</Text>
        {['처방 분석 결과는 대화와 따로, 재분석 안내 시점까지 보관돼요.', '대화 내용은 AI 학습에 쓰이지 않아요.', '삭제한 대화는 서버에서도 30일 이내에 완전히 지워져요.'].map((t) => <Text key={t} style={[T.caption, { color: C.text }]}>· {t}</Text>)}
      </Card>
      <Card style={{ marginTop: 16, gap: 8 }}>
        <Text style={T.bodyM}>대화 기록 전체 삭제</Text>
        <Text style={T.caption}>지금까지의 챗봇 대화를 모두 지워요. 되돌릴 수 없어요.</Text>
        <Btn label="전체 삭제" kind="secondary" onPress={() => setDel(true)} />
      </Card>
      <Confirm visible={del} title="대화 기록을 모두 지울까요?" body="지금까지의 챗봇 대화가 모두 삭제되고 되돌릴 수 없어요. 처방 분석 결과는 지워지지 않아요." ok="삭제"
        onCancel={() => setDel(false)} onOk={() => { set({ chat: [], chatContext: null }); setDel(false); }} />
    </Screen>
  );
}

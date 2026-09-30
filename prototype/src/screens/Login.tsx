import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useApp } from '../store';
import { C, R, T } from '../theme';
import { Btn, Card, Check, Chip, Field, Note, Radio, Screen } from '../ui';

const MAX_FAIL = 5;

// CM-01 로그인 · CM-01-E1 로그인 실패 · CM-01-E2 로그인 잠김
export default function Login() {
  const { s, set, go } = useApp();
  const [email, setEmail] = useState(s.user.email);
  const [pw, setPw] = useState('');
  const [now, setNow] = useState(Date.now());
  const locked = s.lockedUntil && s.lockedUntil > now;
  useEffect(() => {
    if (!s.lockedUntil) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [s.lockedUntil]);

  const login = () => {
    // 프로토타입: 비밀번호 "1234"만 틀린 것으로 처리 (실패 · 잠김 화면 보기용)
    if (pw === '1234' || pw === '') {
      const f = s.loginFails + 1;
      set(f >= MAX_FAIL ? { loginFails: f, lockedUntil: Date.now() + 10 * 60 * 1000 } : { loginFails: f });
      return;
    }
    set({ loggedIn: true, loginFails: 0, lockedUntil: null, user: { ...s.user, email } });
  };
  const left = locked ? Math.max(0, s.lockedUntil! - now) : 0;
  const mmss = `${String(Math.floor(left / 60000)).padStart(2, '0')}:${String(Math.floor((left % 60000) / 1000)).padStart(2, '0')}`;
  const id = locked ? 'CM-01-E2' : s.loginFails > 0 ? 'CM-01-E1' : 'CM-01';

  return (
    <Screen id={id} title="로그인" agendaKey="login" back={false}
      footer={<Btn label={locked ? `로그인  (${mmss} 후 가능)` : '로그인'} disabled={!!locked} onPress={login} />}>
      <View style={{ alignItems: 'center', marginTop: 24, gap: 10 }}>
        <View style={{ width: 72, height: 72, borderRadius: 20, backgroundColor: C.p600, alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: '#fff', fontSize: 30, fontWeight: '800' }}>약</Text></View>
        <Text style={T.title}>약 안내 도우미</Text>
        <Text style={[T.body, { color: C.text2, textAlign: 'center' }]}>처방전을 찍으면 약 정보와 주의사항을 알려드려요</Text>
      </View>
      {locked ? (
        <Card tone="danger" style={{ marginTop: 32, gap: 8 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={T.subhead}>로그인이 잠시 잠겼어요</Text><Chip label="잠김" tone="danger" /></View>
          <Text style={[T.body, { color: C.text }]}>비밀번호를 5번 틀려서 10분 동안 로그인할 수 없어요.</Text>
          <Text style={T.bodyM}>남은 시간  {mmss}</Text>
          <Pressable onPress={() => set({ lockedUntil: null, loginFails: 0 })}><Text style={[T.small, { color: C.text3, marginTop: 4 }]}>(프로토타입) 잠김 풀기</Text></Pressable>
        </Card>
      ) : (
        <View style={{ gap: 16, marginTop: 32 }}>
          <Field label="이메일" value={email} onChangeText={setEmail} placeholder="example@email.com" keyboardType="email-address" />
          <Field label="비밀번호" value={pw} onChangeText={setPw} placeholder="비밀번호 입력" secure />
          {s.loginFails > 0 && (
            <View style={{ gap: 4 }}>
              <Text style={{ fontSize: 14, color: C.danger }}>※ 이메일 또는 비밀번호가 맞지 않아요. ({s.loginFails} / {MAX_FAIL}회)</Text>
              <Text style={{ fontSize: 14, color: C.danger }}>※ 5번 틀리면 10분 동안 로그인할 수 없어요.</Text>
            </View>
          )}
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 8, marginTop: 8 }}>
            <Text style={T.body}>아직 계정이 없으신가요?</Text>
            <Pressable onPress={() => go('signup')}><Text style={[T.bodyM, { color: C.p700 }]}>회원가입</Text></Pressable>
          </View>
        </View>
      )}
      <Note>비밀번호는 아무 값이나 넣으면 로그인돼요. 비워 두거나 "1234"를 넣으면 실패(CM-01-E1), 5번 틀리면 잠김(CM-01-E2) 화면을 볼 수 있어요.</Note>
    </Screen>
  );
}

// CM-02 회원가입 · CM-02-E1 입력 오류
const TERMS = ['[필수] 서비스 이용약관', '[필수] 개인정보 수집 · 이용', '[필수] 민감정보(진료기록) 수집 · 이용'];
export function Signup() {
  const { s, set, toTab } = useApp();
  const [f, setF] = useState({ email: '', pw: '', pw2: '', name: '', year: 0, sex: '' as '' | 'M' | 'F' });
  const [agree, setAgree] = useState([false, false, false]);
  const [err, setErr] = useState<Record<string, string>>({});
  const [yearOpen, setYearOpen] = useState(false);
  const [view, setView] = useState<number | null>(null);
  const all = agree.every(Boolean);

  const submit = () => {
    const e: Record<string, string> = {};
    if (!/.+@.+\..+/.test(f.email)) e.email = '이메일 형식을 확인해 주세요.';
    else if (f.email === 'hong@email.com') e.email = '이미 가입된 이메일이에요. 로그인해 주세요.';
    if (!/(?=.*[A-Za-z])(?=.*\d).{8,}/.test(f.pw)) e.pw = '영문 · 숫자를 넣어 8자 이상으로 만들어 주세요.';
    else if (f.pw !== f.pw2) e.pw2 = '비밀번호가 서로 달라요.';
    if (!f.year) e.year = '출생연도를 선택해 주세요.';
    if (!f.sex) e.sex = '성별을 선택해 주세요.';
    if (!agree[0] || !agree[1]) e.terms = '필수 약관에 동의해 주세요.';
    if (!agree[2]) e.sensitive = '민감정보 수집 · 이용에 동의해야 처방전 분석을 이용할 수 있어요.';
    setErr(e);
    if (Object.keys(e).length) return;
    set({ loggedIn: true, user: { name: f.name || '회원', email: f.email, birthYear: f.year, sex: f.sex as 'M' | 'F' } });
    toTab('home');
  };

  return (
    <Screen id={Object.keys(err).length ? 'CM-02-E1' : 'CM-02'} title="회원가입" agendaKey="login"
      footer={<Btn label="가입하기" onPress={submit} />}>
      <Text style={[T.body, { color: C.text2 }]}>서비스에 꼭 필요한 정보만 받아요.</Text>
      <View style={{ gap: 18, marginTop: 20 }}>
        <Field label="이메일" value={f.email} onChangeText={(v) => setF({ ...f, email: v })} placeholder="example@email.com" helper="로그인할 때 쓰는 아이디예요" error={err.email} keyboardType="email-address" />
        <Field label="비밀번호" value={f.pw} onChangeText={(v) => setF({ ...f, pw: v })} placeholder="영문 · 숫자 포함 8자 이상" secure error={err.pw} />
        <Field label="비밀번호 확인" value={f.pw2} onChangeText={(v) => setF({ ...f, pw2: v })} placeholder="한 번 더 입력" secure error={err.pw2} />
        <Field label="이름 (별명) · 선택" value={f.name} onChangeText={(v) => setF({ ...f, name: v })} placeholder="예) 홍길동" helper="홈 화면 인사말에만 쓰여요" />
        <View style={{ gap: 6 }}>
          <Text style={T.label}>출생연도</Text>
          <Pressable onPress={() => setYearOpen(true)} style={{ borderWidth: 1, borderColor: err.year ? C.danger : C.borderStrong, borderRadius: R.control, padding: 14, backgroundColor: C.card, flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={[T.body, { color: f.year ? C.text : C.text3 }]}>{f.year ? `${f.year}년` : '선택해 주세요'}</Text><Text style={T.body}>▼</Text>
          </Pressable>
          {err.year && <Text style={{ fontSize: 14, color: C.danger }}>※ {err.year}</Text>}
        </View>
        <View style={{ gap: 2 }}>
          <Text style={T.label}>성별</Text>
          <View style={{ flexDirection: 'row' }}><Radio on={f.sex === 'M'} label="남성" onPress={() => setF({ ...f, sex: 'M' })} /><Radio on={f.sex === 'F'} label="여성" onPress={() => setF({ ...f, sex: 'F' })} /></View>
          {err.sex && <Text style={{ fontSize: 14, color: C.danger }}>※ {err.sex}</Text>}
          <Text style={T.caption}>※ 출생연도 · 성별은 어르신이 조심해야 할 약, 나이에 따라 먹으면 안 되는 약을 확인하는 데만 쓰여요.</Text>
        </View>
        <Card style={{ gap: 2 }}>
          <Check on={all} bold label="전체 동의" onPress={() => setAgree(all ? [false, false, false] : [true, true, true])} />
          <View style={{ height: 1, backgroundColor: C.border, marginVertical: 4 }} />
          {TERMS.map((t, i) => (
            <Check key={t} on={agree[i]} label={t} onPress={() => setAgree(agree.map((a, k) => (k === i ? !a : a)))}
              right={<Pressable onPress={() => setView(i)} hitSlop={8}><Text style={[T.caption, { color: C.text2 }]}>보기 {'>'}</Text></Pressable>} />
          ))}
          {(err.terms || err.sensitive) && <Text style={{ fontSize: 14, color: C.danger, marginTop: 4 }}>※ {err.sensitive || err.terms}</Text>}
        </Card>
      </View>
      <Note>"hong@email.com"을 넣으면 이미 가입된 이메일(CM-02-E1)을 볼 수 있어요.</Note>

      <Modal visible={yearOpen} transparent animationType="slide" onRequestClose={() => setYearOpen(false)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(15,23,42,0.35)' }} onPress={() => setYearOpen(false)} />
        <View style={{ backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: 420, padding: 16 }}>
          <Text style={[T.subhead, { marginBottom: 8 }]}>출생연도</Text>
          <ScrollView>{Array.from({ length: 70 }, (_, i) => 1940 + i).map((y) => (
            <Pressable key={y} onPress={() => { setF({ ...f, year: y }); setYearOpen(false); }} style={{ paddingVertical: 12 }}><Text style={[T.body, f.year === y && { color: C.p700, fontWeight: '700' }]}>{y}년</Text></Pressable>
          ))}</ScrollView>
        </View>
      </Modal>
      <Modal visible={view !== null} transparent animationType="fade" onRequestClose={() => setView(null)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(15,23,42,0.45)', justifyContent: 'center', padding: 24 }}>
          <Card style={{ gap: 10 }}>
            <Text style={T.subhead}>{view !== null ? TERMS[view] : ''}</Text>
            <Text style={T.caption}>(프로토타입) 약관 전문 자리예요. 민감정보는 처방전 분석에만 쓰이고, 동의를 철회하면 진료 정보 · 분석 결과 · 챗봇 대화가 지워져요.</Text>
            <Btn label="닫기" kind="secondary" onPress={() => setView(null)} />
          </Card>
        </View>
      </Modal>
    </Screen>
  );
}

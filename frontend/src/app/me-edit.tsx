import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { getMe, updateMe, type Sex } from '@/features/common/api';
import {
  DIALYSIS,
  DISEASE_IDS,
  DRINKING,
  EXAM_NAME_MAX,
  SMOKING,
  type Health,
  type UpcomingExam,
} from '@/features/common/health';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Check, Field, Radio, Screen, Section } from '@/shared/ui';

const c = copy.me;

// CM-06 내 정보 수정 (API 명세서 v1.5 초안 U-2). 이메일은 바꿀 수 없음. 임신 여부는 여성만 (성별을 남성으로 바꾸면 서버가 비움)
export default function MeEdit() {
  const router = useRouter();
  const [birthYear, setBirthYear] = useState('');
  const [sex, setSex] = useState<Sex>('M');
  const [health, setHealth] = useState<Health | null>(null);
  const [height, setHeight] = useState('');
  const [weight, setWeight] = useState('');
  const [examName, setExamName] = useState('');
  const [examDate, setExamDate] = useState('');
  const [fieldError, setFieldError] = useState<{ field: string; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getMe()
      .then((m) => {
        setBirthYear(String(m.birthYear));
        setSex(m.sex);
        setHealth(m.health);
        setHeight(m.health.heightCm ? String(m.health.heightCm) : '');
        setWeight(m.health.weightKg ? String(m.health.weightKg) : '');
      })
      .catch(() => setError(c.loadFailed));
  }, []);

  const set = <K extends keyof Health>(k: K, v: Health[K]) => setHealth((h) => (h ? { ...h, [k]: v } : h));
  const errorOf = (field: string) => (fieldError && fieldError.field.startsWith(field) ? fieldError.message : undefined);
  const Err = ({ field }: { field: string }) =>
    errorOf(field) ? <Text style={{ fontSize: 14, color: C.danger }}>※ {errorOf(field)}</Text> : null;

  const addExam = () => {
    if (!health || examName.trim() === '' || examDate.trim() === '') return;
    set('upcomingExams', [...health.upcomingExams, { name: examName.trim(), date: examDate.trim() }]);
    setExamName('');
    setExamDate('');
  };

  const save = async () => {
    if (!health || busy) return;
    setBusy(true);
    setFieldError(null);
    setError(null);
    // 이름과 날짜를 적고 [검사 추가] 없이 바로 저장해도 잃지 않게 같이 보냄
    const typed = examName.trim() !== '' && examDate.trim() !== '';
    try {
      await updateMe({
        birthYear: Number(birthYear),
        sex,
        health: {
          ...health,
          upcomingExams: typed
            ? [...health.upcomingExams, { name: examName.trim(), date: examDate.trim() }]
            : health.upcomingExams,
          pregnant: sex === 'F' ? health.pregnant : null,
          heightCm: height ? Number(height) : null,
          weightKg: weight ? Number(weight) : null,
        },
      });
      if (router.canGoBack()) router.back();
      else router.replace('/(tabs)/me'); // 웹에서 새로고침하면 돌아갈 곳이 없음
    } catch (e) {
      if (e instanceof ApiError && e.field) setFieldError({ field: e.field, message: e.message });
      else setError(e instanceof ApiError ? e.message : copy.common.serverError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen title={c.editTitle} footer={<Btn label={c.save} disabled={!health || busy} onPress={save} />}>
      {error && <Text style={{ fontSize: 14, color: C.danger }}>※ {error}</Text>}
      {health && (
        <>
          <Section title={copy.signup.basic}>
            <Field
              label={c.birthYear}
              value={birthYear}
              onChangeText={(v) => setBirthYear(v.replace(/\D/g, '').slice(0, 4))}
              keyboardType="number-pad"
              error={errorOf('birthYear')}
            />
            <Text style={T.label}>{c.sex}</Text>
            <View style={{ flexDirection: 'row' }}>
              <Radio on={sex === 'M'} label={copy.signup.male} onPress={() => setSex('M')} />
              <Radio on={sex === 'F'} label={copy.signup.female} onPress={() => setSex('F')} />
            </View>
            <Text style={T.caption}>{c.emailFixed}</Text>
          </Section>

          <Section title={c.smoking}>
            {SMOKING.map((v) => (
              <Radio key={v} on={health.smoking === v} label={copy.health.smoking[v]} onPress={() => set('smoking', v)} />
            ))}
            <Err field="health.smoking" />
          </Section>

          <Section title={c.drinking}>
            {DRINKING.map((v) => (
              <Radio
                key={v}
                on={health.drinking === v}
                label={copy.health.drinking[v]}
                onPress={() => set('drinking', v)}
              />
            ))}
            <Err field="health.drinking" />
          </Section>

          <Section title={c.diseases}>
            <Text style={T.caption}>{c.diseasesHelper}</Text>
            {DISEASE_IDS.map((d) => {
              const on = health.diseases.includes(d);
              return (
                <Check
                  key={d}
                  on={on}
                  label={copy.health.diseases[d]}
                  onPress={() => set('diseases', on ? health.diseases.filter((x) => x !== d) : [...health.diseases, d])}
                />
              );
            })}
            <Err field="health.diseases" />
          </Section>

          {sex === 'F' && (
            <Section title={c.pregnantSection}>
              {(['yes', 'no'] as const).map((v) => (
                <Radio
                  key={v}
                  on={health.pregnant === v}
                  label={copy.health.pregnant[v]}
                  onPress={() => set('pregnant', health.pregnant === v ? null : v)}
                />
              ))}
              <Err field="health.pregnant" />
            </Section>
          )}

          <Section title={c.dialysis}>
            {DIALYSIS.map((v) => (
              <Radio
                key={v}
                on={health.dialysis === v}
                label={copy.health.dialysis[v]}
                onPress={() => set('dialysis', health.dialysis === v ? null : v)}
              />
            ))}
            <Err field="health.dialysis" />
          </Section>

          <Section title={c.body}>
            <Field
              label={c.height}
              value={height}
              onChangeText={(v) => setHeight(v.replace(/\D/g, '').slice(0, 3))}
              keyboardType="number-pad"
              error={errorOf('health.heightCm')}
            />
            <Field
              label={c.weight}
              value={weight}
              onChangeText={(v) => setWeight(v.replace(/[^\d.]/g, '').slice(0, 5))}
              keyboardType="decimal-pad"
              helper={c.weightHelper}
              error={errorOf('health.weightKg')}
            />
          </Section>

          <Section title={c.exams}>
            {health.upcomingExams.length > 0 && (
              <Card style={{ gap: 10 }}>
                {health.upcomingExams.map((e: UpcomingExam, i) => (
                  <View key={`${e.name}-${e.date}-${i}`} style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                    <Text style={T.body}>{`${e.name}, ${c.examDateValue(e.date)}`}</Text>
                    <Pressable
                      accessibilityRole="button"
                      hitSlop={8}
                      onPress={() => set('upcomingExams', health.upcomingExams.filter((_, j) => j !== i))}
                    >
                      <Text style={[T.bodyM, { color: C.danger }]}>{c.examRemove}</Text>
                    </Pressable>
                  </View>
                ))}
              </Card>
            )}
            {/* 검사 추가는 저장과 다른 일이라 입력칸과 버튼을 카드로 묶어 아래 [저장하기]와 나눔 (10/29 멘토님 피드백) */}
            <Card style={{ gap: 10 }}>
              <Field
                label={c.examName}
                value={examName}
                onChangeText={(v) => setExamName(v.slice(0, EXAM_NAME_MAX))}
                helper={c.examNameHelper(EXAM_NAME_MAX)}
              />
              <Field
                label={c.examDate}
                value={examDate}
                onChangeText={setExamDate}
                placeholder="2026-10-27"
                helper={c.examDateHelper}
              />
              <Btn label={c.examAdd} kind="secondary" onPress={addExam} />
            </Card>
            <Err field="health.upcomingExams" />
          </Section>
        </>
      )}
    </Screen>
  );
}

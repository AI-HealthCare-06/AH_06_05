import { useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Modal, Pressable, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { getPrescription, patchItem, searchDrugs } from '@/features/ocr/api';
import { useFlow } from '@/features/ocr/flow';
import type { DrugSearch, MatchStatus, Prescription, PrescriptionItem } from '@/features/ocr/types';
import { copy } from '@/shared/copy';
import { C, R, T } from '@/shared/theme';
import { Btn, Card, Chip, Screen } from '@/shared/ui';

const r = copy.recognize;
const STATUS: Record<MatchStatus, [string, 'success' | 'caution' | 'danger' | 'neutral']> = {
  auto: [r.status.ok, 'success'],
  user_confirmed: [r.status.ok, 'success'],
  needs_confirm: [r.status.confirm, 'caution'],
  unmatched: [r.status.none, 'danger'],
  excluded: [r.status.excluded, 'neutral'],
};

const timing = (it: PrescriptionItem) =>
  [it.timing, it.totalDays ? `${it.totalDays}일` : null].filter(Boolean).join(' · ');

// OC-02 인식 결과 확인 · 수정 (O-2 조회, O-3 수정, O-4 검색)
export default function Recognize() {
  const router = useRouter();
  const { prescriptionIds, duplicates } = useFlow();
  const [list, setList] = useState<Prescription[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [pick, setPick] = useState<Record<number, string | null>>({});
  const [search, setSearch] = useState<{ rxId: number; itemId: number } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setList(await Promise.all(prescriptionIds.map(getPrescription)));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [prescriptionIds]);

  useEffect(() => {
    if (prescriptionIds.length === 0) router.replace('/capture');
    else void load();
  }, [prescriptionIds, load, router]);

  const save = async (rxId: number, itemId: number, body: Record<string, unknown>) => {
    setSaving(true);
    try {
      await patchItem(rxId, itemId, body as never);
      await load();
    } finally {
      setSaving(false);
    }
  };

  if (failed) {
    return (
      <Screen title={r.title} footer={<Btn label={copy.common.retry} onPress={load} />}>
        <Text style={T.body}>{r.loadFail}</Text>
      </Screen>
    );
  }
  if (!list) {
    return (
      <Screen title={r.title}>
        <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />
      </Screen>
    );
  }

  const items = list.flatMap((x) => x.items.map((it) => ({ rx: x, it })));
  const blocking = items.map((v, k) => ({ ...v, k })).filter(({ it }) => it.matchStatus === 'needs_confirm' || it.matchStatus === 'unmatched');
  const usable = items.some(({ it }) => it.matchStatus !== 'excluded' && (it.ediCode || it.itemSeq));
  const codes = [...new Set(list.flatMap((x) => x.diseaseCodes))];
  const notices = list.flatMap((x) => x.notices ?? []);

  return (
    <Screen
      title={r.title}
      footer={
        <View style={{ gap: 6 }}>
          <Btn label={r.start} disabled={blocking.length > 0 || !usable || saving} onPress={() => router.replace('/analyzing')} />
          {blocking.length > 0 && <Text style={[T.caption, { textAlign: 'center' }]}>{r.blocked(blocking.map((b) => `${b.k + 1}번째`).join(' · '))}</Text>}
          <Btn label={r.retake} kind="ghost" onPress={() => router.replace('/capture')} />
        </View>
      }
    >
      <Text style={[T.body, { color: C.text2 }]}>{r.intro}</Text>
      <Text style={[T.bodyM, { marginTop: 8 }]}>{r.summary(list.length, list.map((x) => x.hospitalName ?? '').filter(Boolean).join(', '))}</Text>

      {duplicates.length > 0 && (
        <Text style={[T.caption, { marginTop: 8 }]}>{r.duplicates(duplicates.map((n) => `${n}번째`).join(' · '))}</Text>
      )}
      {notices.length > 0 && (
        <Card tone="caution" style={{ marginTop: 12, gap: 4 }}>
          <Text style={T.label}>{r.noticesTitle}</Text>
          {notices.map((n) => (
            <Text key={n} style={T.caption}>
              · {n}
            </Text>
          ))}
        </Card>
      )}

      <Card tone={codes.length ? 'info' : 'caution'} style={{ marginTop: 12, gap: 4 }}>
        <Text style={T.label}>{r.diseaseTitle}</Text>
        {codes.length ? (
          <>
            <Text style={T.subhead}>{codes.join(', ')}</Text>
            <Text style={T.caption}>{r.diseaseBody}</Text>
          </>
        ) : (
          <Text style={T.caption}>{r.diseaseNone}</Text>
        )}
      </Card>

      <View style={{ gap: 12, marginTop: 14 }}>
        {items.map(({ rx, it }, k) => {
          const [label, tone] = STATUS[it.matchStatus];
          // 후보를 미리 골라 두지 않는다: 사용자가 직접 눌러야 "이 약으로 확인"이 켜진다 (읽은 이름이 다른 약일 수 있는 항목을 그냥 지나치지 않게)
          const chosen = pick[it.id] ?? null;
          const title = it.matchStatus === 'needs_confirm' ? it.rawName : it.itemName ?? (it.matchStatus === 'unmatched' ? `${k + 1}번째 약품` : it.rawName);
          return (
            <Card
              key={it.id}
              tone={it.matchStatus === 'needs_confirm' ? 'caution' : it.matchStatus === 'unmatched' ? 'danger' : undefined}
              style={it.matchStatus === 'excluded' ? { opacity: 0.6 } : undefined}
            >
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <View style={{ flex: 1 }}>
                  <Text style={T.bodyM}>{title}</Text>
                  <Text style={T.caption}>
                    {it.matchStatus === 'unmatched' ? r.rawLabel(it.rawName) : [rx.hospitalName, timing(it)].filter(Boolean).join(' · ')}
                  </Text>
                </View>
                <Chip label={label} tone={tone} />
              </View>

              {it.matchStatus !== 'excluded' && (it.checkFields ?? []).length > 0 && (
                <Text style={[T.caption, { color: C.danger, marginTop: 8 }]}>※ {r.checkFields(it.checkFields.join(', '))}</Text>
              )}

              {it.matchStatus !== 'excluded' && (it.guidance ?? []).length > 0 && (
                <View style={{ marginTop: 8, gap: 2 }}>
                  <Text style={T.label}>{r.guidanceTitle}</Text>
                  {it.guidance.map((g) => (
                    <Text key={g} style={T.caption}>
                      · {g}
                    </Text>
                  ))}
                  <Text style={T.small}>{r.guidanceNote}</Text>
                </View>
              )}

              {(it.matchStatus === 'auto' || it.matchStatus === 'user_confirmed') && (
                <Pressable accessibilityRole="button" hitSlop={8} onPress={() => setSearch({ rxId: rx.id, itemId: it.id })}>
                  <Text style={[T.bodyM, { color: C.p700, marginTop: 8 }]}>{r.edit}</Text>
                </Pressable>
              )}

              {it.matchStatus === 'needs_confirm' && (
                <View style={{ marginTop: 12, gap: 8 }}>
                  <Text style={T.caption}>{it.suggestedBy === 'llm' ? r.suggestedLlm : r.similar}</Text>
                  {it.candidates.map((c) => {
                    const on = chosen === c.ediCode;
                    return (
                      <Pressable
                        key={c.ediCode ?? c.itemSeq ?? c.itemName}
                        accessibilityRole="radio"
                        accessibilityState={{ checked: on }}
                        onPress={() => setPick({ ...pick, [it.id]: c.ediCode })}
                        style={[st.option, { borderColor: on ? C.p600 : C.border }]}
                      >
                        <Text style={{ fontSize: 18, color: on ? C.p600 : C.text2 }}>{on ? '●' : '○'}</Text>
                        <Text style={[T.label, { flex: 1 }]}>{c.itemName}</Text>
                        <Text style={T.caption}>{r.similarity(Math.round(c.score * 100))}</Text>
                      </Pressable>
                    );
                  })}
                  <Pressable accessibilityRole="button" onPress={() => setSearch({ rxId: rx.id, itemId: it.id })} style={[st.option, { borderColor: C.border }]}>
                    <Text style={{ fontSize: 18, color: C.text2 }}>○</Text>
                    <Text style={T.label}>{r.notInList}</Text>
                  </Pressable>
                  <Btn label={r.confirmThis} disabled={!chosen || saving} onPress={() => save(rx.id, it.id, { ediCode: chosen })} />
                  <Btn label={r.exclude} kind="ghost" onPress={() => save(rx.id, it.id, { exclude: true, ediCode: null, itemSeq: null })} />
                </View>
              )}

              {it.matchStatus === 'unmatched' && (
                <View style={{ marginTop: 12, gap: 8 }}>
                  <Pressable accessibilityRole="button" onPress={() => setSearch({ rxId: rx.id, itemId: it.id })} style={st.input}>
                    <Text style={[T.body, { color: C.text2 }]}>{r.typeName}</Text>
                  </Pressable>
                  <Btn label={r.exclude} kind="ghost" onPress={() => save(rx.id, it.id, { exclude: true, ediCode: null, itemSeq: null })} />
                </View>
              )}

              {it.matchStatus === 'excluded' && (
                <Pressable accessibilityRole="button" hitSlop={8} onPress={() => setSearch({ rxId: rx.id, itemId: it.id })}>
                  <Text style={[T.bodyM, { color: C.p700, marginTop: 8 }]}>{r.undo}</Text>
                </Pressable>
              )}
            </Card>
          );
        })}
      </View>
      {blocking.length > 0 && <Text style={[T.caption, { marginTop: 12 }]}>{r.lowConfidence}</Text>}

      <SearchModal
        visible={search !== null}
        onClose={() => setSearch(null)}
        onPick={async (edi) => {
          if (search) await save(search.rxId, search.itemId, { ediCode: edi });
          setSearch(null);
        }}
      />
    </Screen>
  );
}

// O-4 약 이름 검색 (300ms 쉬었다가 호출)
function SearchModal({ visible, onClose, onPick }: { visible: boolean; onClose: () => void; onPick: (edi: string | null) => void }) {
  const ins = useSafeAreaInsets();
  const [q, setQ] = useState('');
  const [res, setRes] = useState<DrugSearch | null>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setRes(null);
      return;
    }
    let live = true;
    const t = setTimeout(() => {
      searchDrugs(q.trim(), 8)
        .then((v) => live && setRes(v))
        .catch(() => live && setRes(null));
    }, 300);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q]);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: C.bg, paddingTop: ins.top + 8 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingBottom: 10 }}>
          <Pressable accessibilityRole="button" accessibilityLabel={copy.common.back} onPress={onClose} hitSlop={12} style={{ minWidth: 32, minHeight: 48, justifyContent: 'center' }}>
            <Text style={{ fontSize: 28, color: C.text }}>‹</Text>
          </Pressable>
          <TextInput
            autoFocus
            value={q}
            onChangeText={setQ}
            placeholder={r.searchPlaceholder}
            placeholderTextColor={C.text2}
            style={[st.input, { flex: 1, color: C.text }]}
          />
        </View>
        <Text style={[T.caption, { paddingHorizontal: 20, marginBottom: 6 }]}>{r.searchHint}</Text>
        <FlatList
          data={res?.items ?? []}
          keyExtractor={(d) => d.ediCode ?? d.itemSeq ?? d.itemName}
          contentContainerStyle={{ padding: 16, gap: 8 }}
          renderItem={({ item }) => (
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                onPick(item.ediCode);
                setQ('');
              }}
              style={st.result}
            >
              <Text style={T.label}>{item.itemName}</Text>
              <Text style={T.caption}>{item.entpName} · {item.etcOtc}</Text>
            </Pressable>
          )}
          ListEmptyComponent={res?.status === 'not_found' ? <Text style={[T.caption, { textAlign: 'center' }]}>{r.searchEmpty}</Text> : null}
        />
      </View>
    </Modal>
  );
}

const st = {
  option: { flexDirection: 'row' as const, gap: 10, alignItems: 'center' as const, backgroundColor: C.card, borderWidth: 1.5, borderRadius: R.control, padding: 12, minHeight: 48 },
  input: { borderWidth: 1, borderColor: C.borderStrong, borderRadius: R.control, padding: 14, backgroundColor: C.card, fontSize: 16 },
  result: { backgroundColor: C.card, borderRadius: R.control, padding: 14, borderWidth: 1, borderColor: C.border, minHeight: 48 },
};

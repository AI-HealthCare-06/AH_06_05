import React, { useState } from 'react';
import { FlatList, Modal, Pressable, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getDrug, searchDrugs, shortName } from '../dur';
import { RxItem, SIMILARITY } from '../scenario';
import { useApp } from '../store';
import { C, R, T } from '../theme';
import { Btn, Card, Chip, Note, Screen } from '../ui';

const STATUS: Record<string, [string, any]> = {
  auto: ['확인됨', 'success'], user_confirmed: ['확인됨', 'success'], needs_confirm: ['확인 필요', 'caution'], unmatched: ['찾지 못함', 'danger'], excluded: ['빼고 진행', 'neutral'],
};

// OC-02 인식 결과 확인 · 수정 (Figma 04 OCR)
export default function Recognize({ search: openSearch }: { search?: boolean }) {
  const { s, set, replace, runAnalysis, back } = useApp();
  const [pick, setPick] = useState<Record<string, string>>({});
  const [searchFor, setSearchFor] = useState<string | null>(openSearch ? 'new' : null);

  const upd = (id: string, p: Partial<RxItem>) => set((st) => ({ items: st.items.map((i) => (i.id === id ? { ...i, ...p } : i)) }));
  const blocking = s.items.map((it, k) => ({ it, k })).filter(({ it }) => it.status === 'needs_confirm' || it.status === 'unmatched');
  const hospitals = s.rxs.map((r) => r.hospital).join(', ');

  const onPicked = (edi: string) => {
    if (searchFor === 'new') set((st) => ({ items: [...st.items, { id: `m${Date.now()}`, rxId: 'manual', raw: '(직접 입력)', edi, status: 'user_confirmed', dose: '—', timing: '용법을 입력해 주세요', days: 0 }] }));
    else if (searchFor) upd(searchFor, { edi, status: 'user_confirmed' });
    setSearchFor(null);
  };

  return (
    <Screen id="OC-02" title="인식 결과 확인" agendaKey="recognize"
      footer={<View style={{ gap: 6 }}>
        <Btn label="확인 완료 · 분석 시작하기" disabled={!!blocking.length || !s.items.length} onPress={() => { runAnalysis(); replace('analyzing'); }} />
        {blocking.length > 0 && <Text style={[T.caption, { textAlign: 'center' }]}>※ {blocking.map((b) => `${b.k + 1}번째`).join(' · ')} 약을 확인하거나 "빼고 진행"을 골라야 시작할 수 있어요</Text>}
        <Btn label="전체 다시 촬영하기" kind="ghost" onPress={back} />
      </View>}>
      <Text style={[T.body, { color: C.text2 }]}>인식한 내용을 확인하고, 잘못된 부분은 수정해 주세요.</Text>
      {s.rxs.length > 0 && <Text style={[T.bodyM, { marginTop: 8 }]}>처방전 {s.rxs.length}장 · {hospitals}</Text>}

      <View style={{ gap: 12, marginTop: 14 }}>
        {s.items.map((it, k) => {
          const d = it.edi ? getDrug(it.edi) : undefined;
          const [lbl, tone] = STATUS[it.status];
          const rx = s.rxs.find((r) => r.id === it.rxId);
          const chosen = pick[it.id] ?? it.candidates?.[0];
          const title = d ? shortName(d.name) : it.status === 'unmatched' ? `${k + 1}번째 약품` : it.raw;
          return (
            <Card key={it.id} tone={it.status === 'needs_confirm' ? 'caution' : it.status === 'unmatched' ? 'danger' : undefined} style={it.status === 'excluded' ? { opacity: 0.6 } : undefined}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <View style={{ flex: 1 }}>
                  <Text style={T.bodyM}>{it.status === 'needs_confirm' ? it.raw : title}</Text>
                  {it.status !== 'unmatched' && <Text style={T.caption}>{rx?.hospital || '직접 추가'} · {it.timing}{it.days ? ` · ${it.days}일` : ''}</Text>}
                  {it.status === 'unmatched' && <Text style={T.caption}>처방전 표기: {it.raw}</Text>}
                </View>
                <Chip label={lbl} tone={tone} />
              </View>
              {(it.status === 'auto' || it.status === 'user_confirmed') && (
                <Pressable onPress={() => setSearchFor(it.id)}><Text style={{ color: C.p700, fontWeight: '600', marginTop: 8 }}>수정</Text></Pressable>
              )}

              {it.status === 'needs_confirm' && (
                <View style={{ marginTop: 12, gap: 8 }}>
                  <Text style={[T.caption, { color: C.text }]}>이름이 비슷한 약이 있어요. 맞는 약을 직접 골라 주세요.</Text>
                  {it.candidates!.map((e, j) => {
                    const cd = getDrug(e)!;
                    const on = chosen === e;
                    return (
                      <Pressable key={e} onPress={() => setPick({ ...pick, [it.id]: e })} style={{ flexDirection: 'row', gap: 10, alignItems: 'center', backgroundColor: C.card, borderWidth: 1.5, borderColor: on ? C.p600 : C.border, borderRadius: R.control, padding: 12 }}>
                        <Text style={{ fontSize: 18, color: on ? C.p600 : C.text3 }}>{on ? '●' : '○'}</Text>
                        <Text style={[T.label, { flex: 1 }]}>{shortName(cd.name)}</Text>
                        <Text style={T.caption}>{j === 0 ? `유사도 ${SIMILARITY[j]}%` : `${SIMILARITY[j]}%`}</Text>
                      </Pressable>
                    );
                  })}
                  <Pressable onPress={() => setSearchFor(it.id)} style={{ flexDirection: 'row', gap: 10, alignItems: 'center', backgroundColor: C.card, borderWidth: 1.5, borderColor: C.border, borderRadius: R.control, padding: 12 }}>
                    <Text style={{ fontSize: 18, color: C.text3 }}>○</Text><Text style={T.label}>목록에 없음 — 직접 입력하기</Text>
                  </Pressable>
                  <Btn label="이 약으로 확인" onPress={() => upd(it.id, { edi: chosen, status: 'user_confirmed' })} />
                  <Pressable onPress={() => upd(it.id, { status: 'excluded' })}><Text style={{ color: C.text2, textAlign: 'center', paddingVertical: 6 }}>이 약은 빼고 진행 {'>'}</Text></Pressable>
                </View>
              )}
              {it.status === 'unmatched' && (
                <View style={{ marginTop: 12, gap: 8 }}>
                  <Pressable onPress={() => setSearchFor(it.id)} style={{ borderWidth: 1, borderColor: C.borderStrong, borderRadius: R.control, padding: 14, backgroundColor: C.card }}>
                    <Text style={[T.body, { color: C.text3 }]}>약 이름을 입력해 주세요</Text>
                  </Pressable>
                  <Pressable onPress={() => upd(it.id, { status: 'excluded' })}><Text style={{ color: C.text2, textAlign: 'center', paddingVertical: 6 }}>이 약은 빼고 진행 {'>'}</Text></Pressable>
                </View>
              )}
              {it.status === 'excluded' && (
                <Pressable onPress={() => upd(it.id, { status: it.edi ? 'user_confirmed' : it.candidates ? 'needs_confirm' : 'unmatched' })}><Text style={{ color: C.p700, marginTop: 8, fontWeight: '600' }}>되돌리기</Text></Pressable>
              )}
            </Card>
          );
        })}
      </View>
      {blocking.length > 0 && <Text style={[T.caption, { marginTop: 12 }]}>※ 인식률이 낮은 항목이 있어요. 다시 확인해 주세요.</Text>}
      <Btn label="+ 약 직접 추가하기" kind="ghost" onPress={() => setSearchFor('new')} style={{ marginTop: 8 }} />
      <Note>약 이름 검색은 실제 심평원 약제급여목록(먹는 약 17,450개)이에요. 유사도 %는 예시 값이에요. "빼고 진행"한 약은 점검에서 빠지고 결과 맨 위에 표시돼요 (REQ-032).</Note>

      <SearchModal visible={!!searchFor} onClose={() => setSearchFor(null)} onPick={onPicked} />
    </Screen>
  );
}

function SearchModal({ visible, onClose, onPick }: { visible: boolean; onClose: () => void; onPick: (edi: string) => void }) {
  const [q, setQ] = useState('');
  const ins = useSafeAreaInsets();
  const res = searchDrugs(q, 30);
  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: C.bg, paddingTop: ins.top + 8 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingBottom: 10 }}>
          <Pressable onPress={onClose} hitSlop={12}><Text style={{ fontSize: 26 }}>‹</Text></Pressable>
          <TextInput autoFocus value={q} onChangeText={setQ} placeholder="약 이름 검색 (예: 코대원, 타이레놀)" placeholderTextColor={C.text3}
            style={{ flex: 1, borderWidth: 1, borderColor: C.borderStrong, borderRadius: R.control, padding: 12, fontSize: 16, backgroundColor: C.card, color: C.text }} />
        </View>
        <Text style={[T.small, { paddingHorizontal: 20, marginBottom: 6 }]}>입력하면 비슷한 약 이름을 추천해 드려요 (O-4 · 2글자 이상)</Text>
        <FlatList data={res} keyExtractor={(d) => d.edi} contentContainerStyle={{ padding: 16, gap: 8 }}
          renderItem={({ item }) => (
            <Pressable onPress={() => { onPick(item.edi); setQ(''); }} style={{ backgroundColor: C.card, borderRadius: R.control, padding: 14, borderWidth: 1, borderColor: C.border }}>
              <Text style={T.label}>{shortName(item.name)}</Text>
              <Text style={T.caption}>{item.entp} · {item.kind}</Text>
            </Pressable>
          )}
          ListEmptyComponent={q.length >= 2 ? <Text style={[T.caption, { textAlign: 'center' }]}>찾는 약이 없어요</Text> : null} />
      </View>
    </Modal>
  );
}

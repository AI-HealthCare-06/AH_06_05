import React, { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Linking, Modal, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { getDrug, shortName } from '../dur';
import { ChatMsg, TODAY, useApp } from '../store';
import { C, R, T } from '../theme';
import { Btn, Chip, Screen, st } from '../ui';

// 답변 종류 8가지 (Figma 05 챗봇 정책) — API · ERD는 아직 3가지 (안건 #16)
const TYPE: Record<string, [string | null, any, string]> = {
  normal: [null, 'info', 'CB-01'], clarify: ['정보 확인', 'neutral', 'CB-01-E3'], partial: ['일부만 확인됐어요', 'caution', 'CB-01-E3'],
  no_evidence: ['확인이 어렵습니다', 'neutral', 'CB-01'], refer: ['의료진 상담 필요', 'caution', 'CB-01'], emergency: ['긴급 안내', 'danger', 'CB-01-E4'],
  crisis: ['도움 연결', 'info', 'CB-01-E5'], error: ['연결 오류', 'neutral', 'CB-01-E6'],
};
const SUGGEST = ['약은 언제 먹는 게 좋나요?', '약은 어떻게 보관해야 하나요?', '복용 중 주의할 점이 있나요?'];

let seq = 0;
const bot = (type: string, text: string, extra: Partial<ChatMsg> = {}): ChatMsg => ({ id: `b${seq++}`, role: 'bot', type, text, ...extra });

// CB-01 대화 · E1 첫 대화 · E2 분석 결과를 아는 대화 · E3 재질문 · E4 긴급 · E5 도움 연결 · E6 오류
export default function Chat() {
  const { s, set } = useApp();
  const [q, setQ] = useState('');
  const [typing, setTyping] = useState(false);
  const [attach, setAttach] = useState(false);
  const [voice, setVoice] = useState<null | 'ask' | 'listen'>(null);
  const [micAsked, setMicAsked] = useState(false);
  const ref = useRef<ScrollView>(null);
  const myDrugs = s.items.filter((i) => i.edi && i.status !== 'excluded').map((i) => shortName(getDrug(i.edi!)!.name));
  const ctx = s.chatContext;

  useEffect(() => {
    if (ctx && !s.chat.some((m) => m.id === `ctx-${ctx.title}`)) {
      const w = s.analysis?.warnings.find((x) => x.drugs.map((d) => d.name).join(' + ') === ctx.title);
      const text = w
        ? `${ctx.title.replace(' + ', '과(와) ')}은(는) 함께 쓰지 않도록 정해진 조합이에요. ${w.summary} 처방한 의사나 약사에게 꼭 알려 주세요.`
        : `${ctx.title}에 대해 물어보세요. 분석한 처방 내용을 알고 답해요.`;
      set((st) => ({ chat: [...st.chat, { id: `ctx-${ctx.title}`, role: 'bot', type: 'normal', context: ctx.title, text, source: w?.source || '식약처 의약품 허가정보', chips: w ? ['근육 이상은 어떤 증상으로 나타나나요?', '의사 · 약사에게 어떻게 말하면 되나요?'] : undefined }] }));
    }
  }, [ctx]);

  const reply = (text: string): ChatMsg => {
    const t = text.replace(/\s/g, '');
    if (/가슴|숨쉬|호흡|의식|마비|어눌|출혈|입술|얼굴이붓|과다복용|많이먹었|한꺼번에/.test(t)) return bot('emergency', '말씀하신 증상은 응급일 수 있어요. 지금 바로 119에 전화하거나 가까운 응급실로 가 주세요.', { actions: ['119 전화하기', '가까운 응급실 찾기'], chips: ['지금은 증상이 없어요'], source: undefined });
    if (/죽고|사라지고|자살|자해|살기싫/.test(t)) return bot('crisis', '많이 힘드셨겠어요. 말씀해 주셔서 고마워요. 지금 마음을 전문 상담사와 이야기해 볼 수 있어요. 자살예방상담전화 109는 24시간 연결돼요.', { actions: ['109 전화하기', '지금 위험하다면 119'] });
    if (/오류/.test(t)) return bot('error', '답변을 만들지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요.', { actions: ['다시 시도'] });
    if (/지금은증상이없어요/.test(t)) return bot('normal', '다행이에요. 다시 증상이 생기면 바로 119에 연락해 주세요. 복약에 관한 질문은 계속 하실 수 있어요.');
    if (/끊어도|그만먹|용량|두배|더먹어도|진단/.test(t)) return bot('refer', '약을 끊거나 바꾸는 판단은 처방한 의사와 먼저 상의해 주세요. 일반적인 복약 정보는 안내할 수 있어요.');
    if (/영양제|홍삼|한약|건강기능/.test(t)) return bot('no_evidence', '등록된 자료에서 이 질문에 대한 근거를 찾지 못했어요. 확인되지 않은 정보는 안내하지 않아요. 약사에게 확인해 주세요.');
    if (/감기약/.test(t) && !/종합|해열|기침/.test(t)) return bot('clarify', '정확한 안내를 위해 두 가지만 확인할게요.\n① 지금 드시는 약: ' + (myDrugs[0] || '직접 입력') + '\n② 감기약 종류를 골라 주세요.', { chips: ['종합감기약', '해열진통제', '기침약', '잘 모르겠어요'] });
    if (/종합감기약|해열진통제|기침약|잘모르겠어요/.test(t)) return bot('partial', '자료에서 확인된 내용은 여기까지예요. 슈도에페드린 성분이 든 감기약은 혈압을 올릴 수 있어 혈압약과 함께 드실 때 주의가 필요해요.\n\n제품별 성분 조합은 자료에서 확인되지 않아 안내하지 않아요. 약국에서 제품을 보여 주고 확인해 주세요.', { source: '식약처 의약품 허가정보' });
    if (/근육/.test(t)) return bot('normal', '근육이 아프거나 힘이 빠지고, 소변 색이 콜라처럼 진해지면 근육이 상하는 부작용일 수 있어요. 이런 증상이 있으면 빨리 진료를 받아 주세요.', { source: '식약처 의약품 허가정보' });
    if (/어떻게말하면/.test(t)) return bot('normal', '"다른 병원에서 받은 클래리스로마이신과 심바스타틴을 같이 먹고 있어요"라고 두 약 이름을 함께 말씀해 주세요. 약봉투를 가져가면 더 정확해요.');
    if (/보관/.test(t)) return bot('normal', '대부분의 알약은 습기와 햇빛을 피해 실온에 보관해요. 욕실이나 차 안처럼 덥고 습한 곳은 피해 주세요.', { source: '식약처 의약품 허가정보' });
    if (/언제먹|식후|식전|밥/.test(t)) return bot('normal', `${myDrugs.find((d) => /노바스크/.test(d)) ? '노바스크정은 식사와 관계없이 드셔도 돼요. ' : ''}매일 같은 시간에 드시는 게 좋아요. 약봉투에 적힌 시간(식후 등)을 따라 주세요.`, { source: '식약처 의약품 허가정보' });
    if (/주의할점/.test(t)) return bot('normal', '지금 드시는 약 중에 함께 먹으면 안 되는 조합이 있어요. 분석 결과의 안전성 탭에서 먼저 확인해 주세요.', { source: '식약처 병용금기 고시' });
    return bot('normal', '처방전에 적힌 대로 드시는 게 가장 안전해요. 개인 상황에 따라 달라질 수 있으니 더 궁금하면 약사에게 물어보세요.', { source: '식약처 의약품 허가정보' });
  };

  const send = (text: string) => {
    if (!text.trim()) return;
    set((st) => ({ chat: [...st.chat, { id: `u${seq++}`, role: 'user', text }] }));
    setQ('');
    setTyping(true);
    setTimeout(() => { setTyping(false); set((st) => ({ chat: [...st.chat, reply(text)] })); }, 700);
  };
  const act = (a: string) => {
    if (a.includes('119')) Linking.openURL('tel:119');
    else if (a.includes('109')) Linking.openURL('tel:109');
    else if (a.includes('응급실')) Linking.openURL('https://www.e-gen.or.kr');
    else if (a === '다시 시도') set((st) => ({ chat: [...st.chat, bot('normal', '다시 보냈어요. (프로토타입: 같은 질문은 요청 ID로 한 번만 저장 — 안건 #19)')] }));
  };

  const lastBot = [...s.chat].reverse().find((m) => m.role === 'bot');
  const id = !s.chat.length ? 'CB-01-E1' : lastBot?.context && s.chat.length <= 1 ? 'CB-01-E2' : TYPE[lastBot?.type || 'normal'][2];

  return (
    <Screen id={voice ? (voice === 'ask' ? 'CB-05-P' : 'CB-05') : attach ? 'CB-04' : id} title="AI 챗봇" agendaKey="chat" scroll={false}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        <ScrollView ref={ref} contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: 110 }} onContentSizeChange={() => ref.current?.scrollToEnd({ animated: true })}>
          {!s.chat.length && (
            <View style={{ gap: 10, marginTop: 8 }}>
              <Text style={T.title}>무엇이든 물어보세요</Text>
              <Text style={[T.body, { color: C.text2 }]}>복용 중인 약과 생활습관에 대해 답해 드려요</Text>
              <Text style={[T.caption, { marginTop: 16 }]}>아직 나눈 대화가 없어요</Text>
              <Text style={T.small}>이런 질문으로 시작해 보세요</Text>
              {SUGGEST.map((x) => <Pressable key={x} onPress={() => send(x)} style={{ backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: R.control, padding: 14 }}><Text style={T.body}>{x}</Text></Pressable>)}
              <Text style={[T.caption, { marginTop: 8 }]}>AI 답변은 정보 제공용이며 의사 · 약사의 진단이나 처방을 대신하지 않아요.</Text>
              <Text style={[T.small, { color: C.text3, marginTop: 8 }]}>(프로토타입) 이렇게도 시험해 보세요: "감기약이랑 같이 먹어도 되나요?" · "약 먹고 가슴이 조여요" · "사라지고 싶어요" · "홍삼" · "오류"</Text>
            </View>
          )}
          {s.chat.map((m) => m.role === 'user' ? (
            <View key={m.id} style={{ alignSelf: 'flex-end', maxWidth: '82%', backgroundColor: C.p600, borderRadius: 16, borderBottomRightRadius: 4, padding: 12 }}><Text style={{ color: '#fff', fontSize: 16, lineHeight: 23 }}>{m.text}</Text></View>
          ) : (
            <View key={m.id} style={{ gap: 6 }}>
              {m.context && (
                <View style={[st.card, { backgroundColor: C.p50, borderColor: C.p100, gap: 4 }]}>
                  <Text style={[T.label, { color: C.p700 }]}>분석 결과를 알고 있어요</Text>
                  <Text style={T.caption}>{TODAY.short} 분석 · 약 {myDrugs.length}개 · 경고 {s.analysis?.warnings.length || 0}건</Text>
                  <Text style={T.caption}>질문 중인 {s.chatContext?.kind === 'drug' ? '약' : '경고'} · {m.context}</Text>
                </View>
              )}
              <View style={{ alignSelf: 'flex-start', maxWidth: '92%', backgroundColor: m.type === 'emergency' ? C.dangerBg : C.card, borderWidth: m.type === 'emergency' ? 1.5 : 1, borderColor: m.type === 'emergency' ? C.danger : C.border, borderRadius: 16, borderBottomLeftRadius: 4, padding: 14, gap: 8 }}>
                {TYPE[m.type || 'normal'][0] && <Chip label={TYPE[m.type || 'normal'][0]!} tone={TYPE[m.type || 'normal'][1]} />}
                <Text style={T.body}>{m.text}</Text>
                {m.type === 'emergency' && <Text style={T.caption}>응급일 수 있는 상황에서는 복약 정보 답변을 이어 가지 않아요.</Text>}
                {m.type === 'crisis' && <Text style={T.caption}>복약에 관한 질문은 언제든 다시 하실 수 있어요.</Text>}
                {m.type === 'error' && <Text style={T.caption}>보낸 질문은 그대로 남아 있어요.</Text>}
                {m.source && <Text style={T.small}>출처 · {m.source} 〉</Text>}
                {m.actions?.map((a) => <Pressable key={a} onPress={() => act(a)} style={{ backgroundColor: m.type === 'emergency' ? C.danger : C.p600, borderRadius: R.control, padding: 12, alignItems: 'center' }}><Text style={{ color: '#fff', fontWeight: '700', fontSize: 16 }}>{a}</Text></Pressable>)}
                {m.type === 'normal' && !m.context && (
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {['도움 됐어요', '답변이 이상해요'].map((b) => <View key={b} style={{ borderWidth: 1, borderColor: C.border, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 }}><Text style={T.small}>{b}</Text></View>)}
                  </View>
                )}
              </View>
              {m.chips && (
                <View style={{ gap: 6 }}>
                  {m.context && <Text style={T.small}>이어서 물어볼 수 있어요</Text>}
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{m.chips.map((c) => <Pressable key={c} onPress={() => send(c)} style={{ borderWidth: 1, borderColor: C.p600, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: C.card }}><Text style={{ color: C.p700, fontWeight: '600' }}>{c}</Text></Pressable>)}</View>
                </View>
              )}
            </View>
          ))}
          {typing && <Text style={T.caption}>●  ●  ●   답변을 만들고 있어요</Text>}
        </ScrollView>
        <View style={{ flexDirection: 'row', gap: 8, padding: 12, backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border, alignItems: 'center' }}>
          <Pressable onPress={() => setAttach(true)} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: C.muted, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 22, color: C.text2 }}>+</Text></Pressable>
          <TextInput value={q} onChangeText={setQ} onSubmitEditing={() => send(q)} placeholder="궁금한 점을 입력하세요" placeholderTextColor={C.text3} returnKeyType="send"
            style={{ flex: 1, borderWidth: 1, borderColor: C.borderStrong, borderRadius: 999, paddingHorizontal: 16, paddingVertical: 10, fontSize: 16, color: C.text }} />
          <Pressable onPress={() => setVoice(micAsked ? 'listen' : 'ask')} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: C.muted, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 16 }}>🎤</Text></Pressable>
          <Pressable onPress={() => send(q)} style={{ backgroundColor: C.p600, borderRadius: 20, width: 40, height: 40, alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: '#fff', fontSize: 20, fontWeight: '700' }}>↑</Text></Pressable>
        </View>
      </KeyboardAvoidingView>

      {/* CB-04 첨부 메뉴 */}
      <Modal visible={attach} transparent animationType="slide" onRequestClose={() => setAttach(false)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(15,23,42,0.35)' }} onPress={() => setAttach(false)} />
        <View style={{ backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, gap: 8 }}>
          <Text style={T.caption}>※ 처방전 · 약봉투는 홈의 [처방전 · 약봉투 분석하기]에서 올려 주세요.</Text>
          {['사진 촬영', '갤러리에서 선택', '파일에서 선택'].map((l) => <Btn key={l} label={l} kind="secondary" onPress={() => setAttach(false)} />)}
          <Btn label="취소" kind="ghost" onPress={() => setAttach(false)} />
          <Text style={[T.small, { color: C.text3 }]}>(프로토타입) 첨부는 선택 구현이라 동작하지 않아요</Text>
        </View>
      </Modal>
      {/* CB-05-P 마이크 권한 사전 안내 · CB-05 음성 입력 */}
      <Modal visible={!!voice} transparent animationType="fade" onRequestClose={() => setVoice(null)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, gap: 12 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={T.subhead}>음성으로 질문하기</Text><Pressable onPress={() => setVoice(null)}><Text style={T.subhead}>✕</Text></Pressable></View>
            {voice === 'ask' ? (
              <>
                <Text style={T.heading}>말로 질문하려면 마이크가 필요해요</Text>
                <Text style={[T.body, { color: C.text2 }]}>다음 화면에서 마이크 사용을 허용해 주세요. 음성은 저장되지 않고 글자로만 바뀌어요.</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <Btn label="나중에" kind="secondary" onPress={() => setVoice(null)} style={{ flex: 1 }} />
                  <Btn label="계속" onPress={() => { setMicAsked(true); setVoice('listen'); }} style={{ flex: 1 }} />
                </View>
              </>
            ) : (
              <>
                <Text style={[T.heading, { color: C.p700 }]}>듣고 있어요...</Text>
                <Text style={T.body}>"이 약 먹고 나서 운동해도 되나요..."</Text>
                <Text style={T.caption}>말씀이 끝나면 완료를 눌러 주세요. 인식된 글자는 보내기 전에 고칠 수 있어요. 음성은 저장되지 않아요.</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <Btn label="취소" kind="secondary" onPress={() => setVoice(null)} style={{ flex: 1 }} />
                  <Btn label="완료" onPress={() => { setQ('이 약 먹고 나서 운동해도 되나요?'); setVoice(null); }} style={{ flex: 1 }} />
                </View>
                <Text style={[T.small, { color: C.text3 }]}>(프로토타입) 실제 음성 인식은 없어요 · 음성 입력은 후순위 제안</Text>
              </>
            )}
          </View>
        </View>
      </Modal>
    </Screen>
  );
}

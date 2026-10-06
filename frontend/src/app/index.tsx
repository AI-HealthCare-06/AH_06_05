import { Text } from 'react-native';

import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Chip, Disclaimer, Screen, Section } from '@/shared/ui';

// 임시 첫 화면 — 공통 부품 확인용. #56 내비 뼈대에서 홈(상단 내비 A안)으로 바꿈
export default function Index() {
  return (
    <Screen title={copy.appName} back={false} footer={<Btn label={copy.login.submit} />}>
      <Text style={T.title}>{copy.appName}</Text>
      <Text style={[T.body, { color: C.text2, marginTop: 8 }]}>{copy.login.tagline}</Text>
      <Section title="공통 부품">
        <Card tone="info">
          <Chip label="확인 필요" tone="caution" />
          <Text style={[T.body, { marginTop: 8 }]}>{copy.chatbot.attachNotice}</Text>
        </Card>
        <Btn label={copy.common.retry} kind="secondary" />
      </Section>
      <Disclaimer />
    </Screen>
  );
}

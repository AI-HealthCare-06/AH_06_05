// 오늘 실천을 모두 마치면 뜨는 화면: 다른 화면과 같은 머리말, 카드, 아래 고정 버튼. [홈으로]를 눌러야 홈으로 감
import { Modal, Text, View } from 'react-native';

import { copy } from '@/shared/copy';
import { T } from '@/shared/theme';
import { Btn, Card, Screen } from '@/shared/ui';

const c = copy.challenge;

export function CelebrateScreen({ visible, streakDays, onHome }: { visible: boolean; streakDays: number; onHome: () => void }) {
  return (
    <Modal visible={visible} animationType="fade" statusBarTranslucent onRequestClose={onHome}>
      <Screen title={copy.nav.challenge} back={false} footer={<Btn label={copy.common.goHome} onPress={onHome} />}>
        <Text style={T.heading} accessibilityRole="header">
          {c.allDone}
        </Text>
        <View style={{ height: 16 }} />
        <Card style={{ gap: 6 }}>
          <Text style={T.subhead}>{streakDays >= 2 ? c.streak(streakDays) : c.streakFirst}</Text>
          <Text style={T.body}>{c.cheer}</Text>
        </Card>
      </Screen>
    </Modal>
  );
}

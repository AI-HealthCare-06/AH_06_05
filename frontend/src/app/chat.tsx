import { useRouter } from 'expo-router';
import { Text } from 'react-native';

import { copy } from '@/shared/copy';
import { T } from '@/shared/theme';
import { Screen } from '@/shared/ui';

// CB-01 챗봇 창 (뼈대) — 플로팅 버튼으로 열림
export default function Chat() {
  const router = useRouter();
  return (
    <Screen title={copy.chatbot.title} onBack={() => router.back()}>
      <Text style={T.caption}>{copy.preparing}</Text>
    </Screen>
  );
}

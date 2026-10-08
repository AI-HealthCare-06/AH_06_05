import { Text } from 'react-native';

import { copy } from '@/shared/copy';
import { T } from '@/shared/theme';
import { Screen } from '@/shared/ui';

// RW-02 실천 (뼈대)
export default function Challenge() {
  return (
    <Screen title={copy.nav.challenge} back={false}>
      <Text style={T.caption}>{copy.preparing}</Text>
    </Screen>
  );
}

import { Text } from 'react-native';

import { copy } from '@/shared/copy';
import { T } from '@/shared/theme';
import { Screen } from '@/shared/ui';

// CM-05 내정보 (뼈대)
export default function Me() {
  return (
    <Screen title={copy.nav.me} back={false}>
      <Text style={T.caption}>{copy.preparing}</Text>
    </Screen>
  );
}

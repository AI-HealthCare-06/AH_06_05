import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { ChatLauncherProvider } from '@/features/chatbot/launcher';
import { AuthProvider, useAuth } from '@/features/common/auth';
import { FlowProvider } from '@/features/ocr/flow';

// 로그인하지 않았으면 로그인 화면만, 로그인했으면 나머지 화면만 열림
function RootStack({ signedIn }: { signedIn: boolean }) {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={signedIn}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="chat" options={{ presentation: 'modal' }} />
        <Stack.Screen name="capture" />
        <Stack.Screen name="recognize" />
        <Stack.Screen name="analyzing" options={{ gestureEnabled: false }} />
        <Stack.Screen name="result" options={{ gestureEnabled: false }} />
        <Stack.Screen name="warning" />
        <Stack.Screen name="history" />
        <Stack.Screen name="me-edit" />
        <Stack.Screen name="consents" />
        <Stack.Screen name="withdraw" />
      </Stack.Protected>
      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="login" />
        <Stack.Screen name="signup" />
      </Stack.Protected>
    </Stack>
  );
}

// 저장된 값을 읽는 아주 짧은 동안은 아무것도 그리지 않음 (로그인 화면이나 챗봇 버튼이 잠깐 보이지 않게)
function Root() {
  const { status } = useAuth();
  if (status === 'checking') return null;
  return (
    <FlowProvider>
      <ChatLauncherProvider>
        <RootStack signedIn={status === 'signedIn'} />
        <StatusBar style="dark" />
      </ChatLauncherProvider>
    </FlowProvider>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}

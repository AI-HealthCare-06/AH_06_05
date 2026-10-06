import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { ChatLauncherProvider } from '@/features/chatbot/launcher';

export default function RootLayout() {
  return (
    <ChatLauncherProvider>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="chat" options={{ presentation: 'modal' }} />
      </Stack>
      <StatusBar style="dark" />
    </ChatLauncherProvider>
  );
}

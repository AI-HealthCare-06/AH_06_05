import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import Analyzing from './src/screens/Analyzing';
import Capture from './src/screens/Capture';
import Chat from './src/screens/Chat';
import Exception from './src/screens/Exception';
import Home, { History } from './src/screens/Home';
import Login, { Signup } from './src/screens/Login';
import Me, { Consents, EditProfile, Retention, Withdraw } from './src/screens/Me';
import Recognize from './src/screens/Recognize';
import Result, { WarningDetail } from './src/screens/Result';
import { Goals, Today, Weekly } from './src/screens/Reward';
import { AppProvider, Tab, useApp } from './src/store';
import { C } from './src/theme';

const SCREENS: Record<string, React.ComponentType<any>> = {
  capture: Capture, exception: Exception, recognize: Recognize, analyzing: Analyzing, result: Result,
  warning: WarningDetail, chat: Chat, goals: Goals, weekly: Weekly,
  history: History, editProfile: EditProfile, withdraw: Withdraw, consents: Consents, retention: Retention,
};
const TABS: [Tab, string, React.ComponentType<any>][] = [['home', '홈', Home], ['today', '실천', Today], ['chat', '챗봇', Chat], ['me', '내정보', Me]];

function Router() {
  const { s, stack, tab, toTab } = useApp();
  const ins = useSafeAreaInsets();
  const top = stack[stack.length - 1];
  if (!s.loggedIn) return top?.name === 'signup' ? <Signup /> : <Login />;
  if (top) {
    const Comp = SCREENS[top.name];
    return <Comp {...(top.params || {})} />;
  }
  const Cur = TABS.find((t) => t[0] === tab)![2];
  return (
    <View style={{ flex: 1 }}>
      <Cur />
      {/* 하단 메뉴 고정: 홈 · 실천 · 챗봇 · 내정보 (NFR-023) */}
      <View style={{ flexDirection: 'row', backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border, paddingBottom: ins.bottom || 8, paddingTop: 8 }}>
        {TABS.map(([k, l]) => (
          <Pressable key={k} onPress={() => toTab(k)} style={{ flex: 1, alignItems: 'center', paddingVertical: 6 }}>
            <Text style={{ fontSize: 15, fontWeight: tab === k ? '700' : '500', color: tab === k ? C.p700 : C.text3 }}>{l}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" />
        <Router />
      </AppProvider>
    </SafeAreaProvider>
  );
}

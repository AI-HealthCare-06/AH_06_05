import { StyleSheet, Text, View } from 'react-native';

// 임시 첫 화면 — #56 내비 뼈대에서 홈(상단 내비 A안)으로 바꿈
export default function Index() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>[서비스명]</Text>
      <Text style={styles.body}>frontend 뼈대 준비 중</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F4F7FB' },
  title: { fontSize: 24, fontWeight: '800', color: '#0F172A' },
  body: { marginTop: 8, fontSize: 16, color: '#475569' },
});

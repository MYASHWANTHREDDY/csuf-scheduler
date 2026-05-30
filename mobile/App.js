import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { AuthProvider, useAuth } from "./src/context/AuthContext";
import LoginScreen from "./src/screens/LoginScreen";
import ScheduleScreen from "./src/screens/ScheduleScreen";
import SwapScreen from "./src/screens/SwapScreen";
import AvailabilityScreen from "./src/screens/AvailabilityScreen";
import NotificationsScreen from "./src/screens/NotificationsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";

const TABS = [
  { key: "schedule", label: "Schedule" },
  { key: "swaps", label: "Swaps" },
  { key: "availability", label: "Availability" },
  { key: "notifications", label: "Notifications" },
  { key: "settings", label: "Settings" },
];

function AuthenticatedApp() {
  const [activeTab, setActiveTab] = useState("schedule");

  const content = useMemo(() => {
    if (activeTab === "schedule") {
      return <ScheduleScreen />;
    }
    if (activeTab === "swaps") {
      return <SwapScreen />;
    }
    if (activeTab === "availability") {
      return <AvailabilityScreen />;
    }
    if (activeTab === "notifications") {
      return <NotificationsScreen />;
    }
    return <SettingsScreen />;
  }, [activeTab]);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      <View style={styles.content}>{content}</View>
      <View style={styles.tabBar}>
        {TABS.map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tabButton, activeTab === tab.key ? styles.tabButtonActive : null]}
            onPress={() => setActiveTab(tab.key)}
          >
            <Text style={[styles.tabLabel, activeTab === tab.key ? styles.tabLabelActive : null]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </SafeAreaView>
  );
}

function Root() {
  const { user, initializing } = useAuth();

  if (initializing) {
    return (
      <SafeAreaView style={styles.loaderContainer}>
        <ActivityIndicator size="large" />
      </SafeAreaView>
    );
  }

  if (!user) {
    return <LoginScreen />;
  }

  return <AuthenticatedApp />;
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
  loaderContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f8fafc",
  },
  content: {
    flex: 1,
  },
  tabBar: {
    flexDirection: "row",
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
    backgroundColor: "#ffffff",
    paddingVertical: 6,
  },
  tabButton: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
  },
  tabButtonActive: {
    borderBottomWidth: 2,
    borderBottomColor: "#0f172a",
  },
  tabLabel: {
    fontSize: 12,
    color: "#64748b",
    fontWeight: "600",
  },
  tabLabelActive: {
    color: "#0f172a",
  },
});
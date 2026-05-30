import React from "react";
import { Text } from "react-native";
import { API_BASE_URL } from "../config";
import { useAuth } from "../context/AuthContext";
import { Button, Card, Screen } from "../components/UI";

export default function SettingsScreen() {
  const { user, logout } = useAuth();

  return (
    <Screen title="Settings" subtitle="Profile and session preferences">
      <Card>
        <Text style={{ fontWeight: "700", marginBottom: 8 }}>Profile</Text>
        <Text>Name: {user?.name || "-"}</Text>
        <Text>Email: {user?.email || "-"}</Text>
        <Text>Role: {user?.role || "-"}</Text>
      </Card>

      <Card>
        <Text style={{ fontWeight: "700", marginBottom: 8 }}>Connection</Text>
        <Text>API Base URL:</Text>
        <Text>{API_BASE_URL}</Text>
      </Card>

      <Card>
        <Button text="Sign Out" onPress={logout} />
      </Card>
    </Screen>
  );
}
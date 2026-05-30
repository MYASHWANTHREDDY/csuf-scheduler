import React, { useState } from "react";
import { SafeAreaView, StyleSheet } from "react-native";
import { useAuth } from "../context/AuthContext";
import { Button, Card, InlineError, Input, Screen } from "../components/UI";

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async () => {
    setError("");
    if (!email || !password) {
      setError("Email and password are required.");
      return;
    }
    setSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (submitError) {
      setError(submitError.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Screen
        title="CSUF Scheduler"
        subtitle="Sign in with your existing web credentials"
      >
        <Card>
          <Input
            label="Email"
            value={email}
            onChangeText={setEmail}
            placeholder="name@csu.fullerton.edu"
          />
          <Input
            label="Password"
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••"
            secureTextEntry
          />
          <InlineError message={error} />
          <Button text={submitting ? "Signing in..." : "Sign In"} onPress={onSubmit} disabled={submitting} />
        </Card>
      </Screen>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
});
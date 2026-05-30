import React, { useCallback, useEffect, useState } from "react";
import { Text } from "react-native";
import {
  createAvailability,
  listAvailability,
  normalizeError,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Button, Card, InlineError, Input, Loading, Screen } from "../components/UI";

export default function AvailabilityScreen() {
  const { csrfToken } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [shiftPreference, setShiftPreference] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const nextItems = await listAvailability();
      setItems(nextItems);
    } catch (loadError) {
      setError(normalizeError(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    setError("");
    setSuccess("");
    if (!date || !startTime || !endTime) {
      setError("Date, start time, and end time are required.");
      return;
    }
    setSubmitting(true);
    try {
      await createAvailability(
        {
          date,
          start_time: startTime,
          end_time: endTime,
          is_recurring: false,
          shift_preference: shiftPreference || null,
        },
        csrfToken
      );
      setSuccess("Availability saved.");
      setDate("");
      setStartTime("");
      setEndTime("");
      setShiftPreference("");
      await load();
    } catch (submitError) {
      setError(normalizeError(submitError));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen title="Availability" subtitle="Submit one-time availability windows">
      {loading ? <Loading label="Loading availability..." /> : null}
      <InlineError message={error} />
      {success ? <Text style={{ color: "#166534", marginBottom: 8 }}>{success}</Text> : null}

      <Card>
        <Text style={{ fontWeight: "700", marginBottom: 10 }}>New Availability</Text>
        <Input
          label="Date"
          value={date}
          onChangeText={setDate}
          placeholder="YYYY-MM-DD"
        />
        <Input
          label="Start Time"
          value={startTime}
          onChangeText={setStartTime}
          placeholder="HH:MM"
        />
        <Input
          label="End Time"
          value={endTime}
          onChangeText={setEndTime}
          placeholder="HH:MM"
        />
        <Input
          label="Shift Preference (optional)"
          value={shiftPreference}
          onChangeText={setShiftPreference}
          placeholder="morning / evening"
        />
        <Button text={submitting ? "Saving..." : "Save Availability"} onPress={submit} disabled={submitting} />
      </Card>

      <Card>
        <Text style={{ fontWeight: "700", marginBottom: 8 }}>Existing Availability</Text>
        {items.length === 0 ? <Text>No availability records found.</Text> : null}
        {items.map((item) => (
          <Text key={item.id} style={{ marginBottom: 4 }}>
            #{item.id} • {item.date || `Recurring day ${item.day_of_week}`} • {item.start_time}-{item.end_time}
          </Text>
        ))}
      </Card>
    </Screen>
  );
}
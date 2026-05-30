import React, { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshControl, Text, View } from "react-native";
import { listMyShifts, normalizeError } from "../api/client";
import { Card, InlineError, Loading, Screen } from "../components/UI";

function formatShift(shift) {
  return `${shift.date} • ${shift.start_time} - ${shift.end_time}`;
}

export default function ScheduleScreen() {
  const [shifts, setShifts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const nextShifts = await listMyShifts();
      setShifts(nextShifts);
    } catch (loadError) {
      setError(normalizeError(loadError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  const sorted = useMemo(() => {
    return [...shifts].sort((a, b) => {
      if (a.date === b.date) {
        return a.start_time.localeCompare(b.start_time);
      }
      return a.date.localeCompare(b.date);
    });
  }, [shifts]);

  return (
    <Screen
      title="My Schedule"
      subtitle="Upcoming shifts assigned to your account"
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />
      }
    >
      {loading ? <Loading label="Loading shifts..." /> : null}
      <InlineError message={error} />

      {!loading && sorted.length === 0 ? (
        <Card>
          <Text>No shifts found yet.</Text>
        </Card>
      ) : null}

      {sorted.map((shift) => (
        <Card key={shift.id}>
          <Text style={{ fontWeight: "700", marginBottom: 6 }}>{formatShift(shift)}</Text>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <Text>Shift ID: {shift.id}</Text>
            <Text>Assigned: {shift.assigned_user_id || "Unassigned"}</Text>
          </View>
        </Card>
      ))}
    </Screen>
  );
}
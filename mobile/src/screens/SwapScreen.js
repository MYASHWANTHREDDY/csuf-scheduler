import React, { useCallback, useEffect, useState } from "react";
import { Text } from "react-native";
import {
  createSwapRequest,
  listMyShifts,
  listSwapRequests,
  normalizeError,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Button, Card, InlineError, Input, Loading, Screen } from "../components/UI";

export default function SwapScreen() {
  const { csrfToken } = useAuth();
  const [myShifts, setMyShifts] = useState([]);
  const [swapRequests, setSwapRequests] = useState([]);
  const [shiftId, setShiftId] = useState("");
  const [targetShiftId, setTargetShiftId] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextShifts, nextRequests] = await Promise.all([listMyShifts(), listSwapRequests()]);
      setMyShifts(nextShifts);
      setSwapRequests(nextRequests);
    } catch (loadError) {
      setError(normalizeError(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submitSwapRequest = async () => {
    setError("");
    setSuccess("");
    if (!shiftId) {
      setError("Shift ID is required.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = { shift_id: Number(shiftId) };
      if (targetShiftId) {
        payload.target_shift_id = Number(targetShiftId);
      }
      await createSwapRequest(payload, csrfToken);
      setSuccess("Swap request submitted.");
      setShiftId("");
      setTargetShiftId("");
      await load();
    } catch (submitError) {
      setError(normalizeError(submitError));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen title="Swap Requests" subtitle="Create and track shift swaps">
      {loading ? <Loading label="Loading swap data..." /> : null}
      <InlineError message={error} />
      {success ? <Text style={{ color: "#166534", marginBottom: 8 }}>{success}</Text> : null}

      <Card>
        <Text style={{ fontWeight: "700", marginBottom: 10 }}>New Swap Request</Text>
        <Input
          label="Your Shift ID"
          value={shiftId}
          onChangeText={setShiftId}
          placeholder="e.g. 42"
        />
        <Input
          label="Target Shift ID (optional)"
          value={targetShiftId}
          onChangeText={setTargetShiftId}
          placeholder="e.g. 55"
        />
        <Button
          text={submitting ? "Submitting..." : "Request Swap"}
          onPress={submitSwapRequest}
          disabled={submitting}
        />
      </Card>

      <Card>
        <Text style={{ fontWeight: "700", marginBottom: 8 }}>My Assigned Shifts</Text>
        {myShifts.length === 0 ? <Text>No assigned shifts.</Text> : null}
        {myShifts.map((shift) => (
          <Text key={shift.id} style={{ marginBottom: 4 }}>
            #{shift.id} • {shift.date} {shift.start_time}-{shift.end_time}
          </Text>
        ))}
      </Card>

      <Card>
        <Text style={{ fontWeight: "700", marginBottom: 8 }}>Recent Requests</Text>
        {swapRequests.length === 0 ? <Text>No swap requests yet.</Text> : null}
        {swapRequests.map((request) => (
          <Text key={request.id} style={{ marginBottom: 4 }}>
            #{request.id} • shift #{request.shift_id} • status: {request.status}
          </Text>
        ))}
      </Card>
    </Screen>
  );
}
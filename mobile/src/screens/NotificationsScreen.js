import React, { useCallback, useEffect, useState } from "react";
import { Pressable, Text } from "react-native";
import {
  listNotifications,
  markNotificationSeen,
  normalizeError,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Card, InlineError, Loading, Screen } from "../components/UI";

export default function NotificationsScreen() {
  const { csrfToken } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const notifications = await listNotifications();
      setItems(notifications);
    } catch (loadError) {
      setError(normalizeError(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const markSeen = async (id) => {
    try {
      await markNotificationSeen(id, csrfToken);
      await load();
    } catch (markError) {
      setError(normalizeError(markError));
    }
  };

  return (
    <Screen title="Notifications" subtitle="Recent scheduling alerts">
      {loading ? <Loading label="Loading notifications..." /> : null}
      <InlineError message={error} />
      {items.length === 0 && !loading ? (
        <Card>
          <Text>No notifications right now.</Text>
        </Card>
      ) : null}

      {items.map((item) => (
        <Card key={item.id}>
          <Text style={{ fontWeight: item.seen ? "500" : "700", marginBottom: 6 }}>
            {item.message}
          </Text>
          <Text style={{ color: "#64748b", marginBottom: 8 }}>
            {item.category || "general"} • {item.created_at || ""}
          </Text>
          {!item.seen ? (
            <Pressable onPress={() => markSeen(item.id)}>
              <Text style={{ color: "#0f172a", fontWeight: "700" }}>Mark as seen</Text>
            </Pressable>
          ) : (
            <Text style={{ color: "#16a34a" }}>Seen</Text>
          )}
        </Card>
      ))}
    </Screen>
  );
}
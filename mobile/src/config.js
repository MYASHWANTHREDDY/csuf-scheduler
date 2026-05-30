import { Platform } from "react-native";

function defaultApiBaseUrl() {
  if (Platform.OS === "android") {
    return "http://10.0.2.2:5000";
  }
  return "http://127.0.0.1:5000";
}

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || defaultApiBaseUrl();
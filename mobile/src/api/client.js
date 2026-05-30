import axios from "axios";
import { API_BASE_URL } from "../config";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

function csrfHeaders(csrfToken) {
  if (!csrfToken) {
    return {};
  }
  return { "X-CSRF-Token": csrfToken };
}

function normalizeError(error) {
  const responseData = error?.response?.data;
  if (typeof responseData?.error === "string") {
    return responseData.error;
  }
  if (Array.isArray(responseData?.error) && responseData.error.length > 0) {
    return JSON.stringify(responseData.error);
  }
  return error?.message || "Request failed";
}

export async function login(email, password) {
  try {
    const response = await client.post("/api/users/login", { email, password });
    return response.data;
  } catch (error) {
    throw new Error(normalizeError(error));
  }
}

export async function getCurrentUser() {
  const response = await client.get("/api/users/me");
  return response.data;
}

export async function getCsrfToken() {
  const response = await client.get("/api/users/csrf");
  return response.data?.csrf_token || "";
}

export async function logout(csrfToken) {
  await client.post("/api/users/logout", {}, { headers: csrfHeaders(csrfToken) });
}

export async function listMyShifts() {
  const response = await client.get("/api/shifts");
  return Array.isArray(response.data) ? response.data : response.data.items || [];
}

export async function listSwapRequests() {
  const response = await client.get("/api/swap_requests");
  return response.data || [];
}

export async function createSwapRequest(payload, csrfToken) {
  const response = await client.post("/api/swap_requests", payload, {
    headers: csrfHeaders(csrfToken),
  });
  return response.data;
}

export async function listAvailability() {
  const response = await client.get("/api/availability");
  return response.data || [];
}

export async function createAvailability(payload, csrfToken) {
  const response = await client.post("/api/availability", payload, {
    headers: csrfHeaders(csrfToken),
  });
  return response.data;
}

export async function listNotifications() {
  const response = await client.get("/api/notifications");
  return response.data || [];
}

export async function markNotificationSeen(notificationId, csrfToken) {
  const response = await client.post(
    `/api/notifications/${notificationId}/seen`,
    {},
    { headers: csrfHeaders(csrfToken) }
  );
  return response.data;
}

export { client, normalizeError };
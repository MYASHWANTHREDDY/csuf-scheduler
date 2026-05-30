# CSUF Scheduler Mobile (Phase 7 MVP)

React Native (Expo) mobile client for iOS/Android using the existing CSUF Scheduler backend APIs.

## Implemented MVP Flows

- Login with existing `/api/users/login` credentials
- View assigned shifts from `/api/shifts`
- Create/list swap requests via `/api/swap_requests`
- Submit/list availability via `/api/availability`
- View notifications and mark seen via `/api/notifications`
- Profile/session settings and sign-out

## Prerequisites

- Node.js 18+
- Expo CLI (via `npx expo`)
- Backend running locally (`python scripts/run_dev.py`)

## Setup

```bash
cd mobile
npm install
```

Optional environment override:

```bash
# PowerShell
$env:EXPO_PUBLIC_API_BASE_URL="http://127.0.0.1:5000"
```

Default base URLs:

- iOS simulator: `http://127.0.0.1:5000`
- Android emulator: `http://10.0.2.2:5000`

## Run

```bash
npm run start
```

Then choose `i` (iOS), `a` (Android), or scan QR with Expo Go.

## Auth/CSRF Notes

- Backend auth is session-cookie based.
- Mobile client stores a lightweight session hint and refreshes user/CSRF on app launch.
- Mutating requests send `X-CSRF-Token` using the token returned from login/`/api/users/csrf`.

## Scope

This is Phase 7 MVP implementation (core flows only). Push-device registration endpoints are not present in backend yet, so notification handling currently uses existing in-app notification APIs.
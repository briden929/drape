# FINAL LOGIN STATE MACHINE

States:
- `UNKNOWN`: Initial state
- `CHECKING`: Polling Google Accounts / Gemini
- `LOGGED_IN`: Session valid
- `GOOGLE_LOGIN_REQUIRED`: Hit accounts.google.com
- `GEMINI_LOGIN_REQUIRED`: Hit gemini splash page
- `CHALLENGE_REQUIRED`: 2FA / Phone verification required
- `SESSION_EXPIRED`: Kicked out during job
- `RECOVERING`: Attempting OTP injection
- `FAILED`: Hard failure
- `READY`: Authenticated

Transition Rules:
- If `CHECKING` finds `accounts.google.com/signin`, go to `GOOGLE_LOGIN_REQUIRED`.
- If `CHECKING` finds `rich-textarea` and profile icon, go to `LOGGED_IN`.

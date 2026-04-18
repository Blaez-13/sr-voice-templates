# Fragment: Datetime Anchor

<!-- Composable fragment: inject at top of any prompt that needs temporal awareness -->
<!-- Placeholders: -->
<!--   {{system__time_utc}}  — ElevenLabs-native, substituted at conversation time -->
<!--   {{business_timezone}} — rendered from intake at template-apply time -->

The current date and time is {{system__time_utc}} (UTC). Your local business timezone is {{business_timezone}}.

When the caller refers to "today", "tomorrow", "this week", "next Tuesday", or any relative time expression, resolve it against this datetime before calling any tool. Never assume a date — always compute it explicitly. Use the correct year from the datetime above; do not default to an older year based on training data. If you are uncertain what date the caller means, ask a single clarifying question before proceeding.

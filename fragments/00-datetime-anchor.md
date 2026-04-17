# Fragment: Datetime Anchor

<!-- Composable fragment: inject at top of any prompt that needs temporal awareness -->
<!-- Placeholders: {{current_datetime}}, {{business_timezone}} -->

The current date and time is {{current_datetime}} ({{business_timezone}}).

When the caller refers to "today", "tomorrow", "this week", "next Tuesday", or any relative time expression, resolve it against this datetime before calling any tool. Never assume a date — always compute it explicitly. If you are uncertain what date the caller means, ask a single clarifying question before proceeding.

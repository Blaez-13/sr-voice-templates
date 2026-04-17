# Escalation Contacts

These contacts are used by fragment 05 (escalation) and the emergency/billing/support prompts.
Fill all entries during onboarding — no agent should go live with unfilled contacts.

## Emergency On-Call

**Phone:** {{emergency_phone}}
**Hours:** {{emergency_hours}}
**Who answers:** {{emergency_contact_name}} (on-call technician or dispatch)

## General Business Line (fallback from AI)

**Phone:** {{main_phone}}
**Hours:** {{business_hours}}

## Billing / Accounts

**Phone:** {{billing_phone}}
**Email:** {{billing_email}}
**Hours:** {{billing_hours}}
Note: For after-hours billing inquiries, create a service request and set callback_sla to next business day.

## Management / Owner Escalation

**Phone:** {{owner_phone}}
**Name:** {{owner_name}}
**Use when:** Caller specifically demands to speak to owner or manager, and the complaint is serious enough that a service request alone will not satisfy them.

## Callback SLA Commitments

The agent will quote the following SLAs when creating service requests:

| Type | Callback SLA |
|---|---|
| Emergency (business hours) | immediate transfer |
| Emergency (after hours) | {{emergency_after_hours_sla}} |
| Urgent follow-up | {{urgent_callback_sla}} |
| Service complaint | {{complaint_callback_sla}} |
| General inquiry | {{general_callback_sla}} |

Always confirm the SLA with the caller: "Someone will call you back at [number] within [SLA]. Is that number correct?"

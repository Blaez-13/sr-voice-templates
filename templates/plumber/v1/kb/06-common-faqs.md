# Common FAQs — Plumber v1

These are the most frequently asked questions on plumbing service calls.
Use these answers directly. If a question is not covered here, fall back to the appropriate prompt node.

---

**Q: How soon can someone come out?**
A: "It depends on the day — let me check what's available. Do you have a day in mind?" Then call check_availability.

---

**Q: Is there a fee just to come out and look?**
A: {{dispatch_fee_policy}} (see KB 03 — pricing policy).

---

**Q: Do you do emergency plumbing?**
A: "Yes — for active emergencies like flooding, burst pipes, or sewage backup, we have an emergency line available {{emergency_hours}}. What's going on?"

---

**Q: Are you licensed and insured?**
A: "Yes — {{client_name}} is licensed and insured in {{service_area_primary}}. {{license_number_disclosure}}"

---

**Q: Do you work on commercial properties?**
A: {{commercial_policy}} (set at onboarding: yes/no/call to confirm)

---

**Q: Can you give me a ballpark price for [service]?**
A: See fragment 09 (no-pricing-policy) for exact script.

---

**Q: How long will the job take?**
A: "That depends on what we find — the technician can give you a better estimate when they see it in person. Most [drain cleans / toilet repairs / etc.] are finished in under an hour."

---

**Q: Do you offer financing or payment plans?**
A: {{financing_policy}} (set at onboarding). Default: "We don't currently offer financing — payment is due at time of service."

---

**Q: What should I do right now while I wait for the technician?**
For leaks: "If you can locate your main water shutoff, turning it off will stop the flow. Otherwise, try to contain the water with towels and move valuables out of the affected area."
For clogged drains: "Avoid running water into that drain until the technician arrives."
For gas smell: "Leave the building, don't operate any switches or appliances, and call 911 if you haven't already. Then call {{emergency_phone}}."

---

**Q: Do you have reviews / are you on Google?**
A: {{google_reviews_url}} (set at onboarding). "You can find our reviews at {{google_reviews_url}}."

# Changelog

## Current Local Update

- Added structured household address fields: house/block/lot number, street name, purok/sitio, landmark, and length of residency.
- Added backend and frontend validation that rejects `Unspecified` family income bracket when `No Income` is available.
- Updated resident household-head logic so `Head` role automatically marks the resident as household head and backend blocks multiple heads per household.
- Added lot area support while keeping legacy household size for backward compatibility.
- Added expanded housing, structure, tenure, employment, electrical, and water source options.
- Added barangay staff account fields: position, organization, and account status.
- Improved reports page grouping by report category and clarified report purpose/source.
- Added confirmation prompts before key create/update/report/status actions.
- Added migrations for new household, resident, and staff account fields.
- Added backend validation tests for structured address, income bracket restriction, and household-head uniqueness.
- Split program cycle dates into an application period and a TUPAD work period.
- Applicant marking is now limited to the application period.
- Participation dates are now validated against the TUPAD work period.
- Added daily participation records with status, hours worked, remarks, and optional photo evidence.
- Participation `days_worked` is now computed from daily records marked present.
- Staff and resident participation history views now expose daily attendance/work status.
- Daily attendance is now recorded for the current date only, only inside the cycle work period, and only once per resident per day.

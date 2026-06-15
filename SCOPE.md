# SCOPE.md

## Detected CSV Anomalies

* Duplicate expenses
* Missing fields
* Invalid amounts
* Negative amounts
* Zero amounts
* Mixed date formats
* Ambiguous dates
* Currency inconsistencies
* Unknown users
* Participant mismatches
* Settlement disguised as expense
* Split inconsistencies
* Name normalization issues
* Expenses outside membership periods

## Handling Policies

Duplicates:
Flagged for approval before merge/removal.

Negative amounts:
Handled as refunds.

Zero amounts:
Skipped and reported.

Mixed dates:
Parsed using documented precedence and flagged.

USD entries:
Converted using INR exchange rate of 83.50.

Unknown users:
Flagged for user review.

Settlement rows:
Converted into settlement records.

Membership violations:
Excluded from balance calculations.

## Database Schema

Core entities:

* User
* Group
* GroupMembership
* Expense
* ExpenseSplit
* Balance
* Settlement
* Message
* ImportSession
* ImportIssue

# Public eBay identity expansion v1

This fixture broadens the original 15-row SOLD bootstrap to 30 genuine public `ebay.com/itm/...` pages, balanced across the six current canonical Opportunity assets.

The evidence claim is intentionally narrow:

- The original sold-bootstrap rows retain their prior labels and limited visible-price metadata.
- Added rows are used **only for card-identity resolution**. They may be active, ended, or product-backed public item pages and have `price_usable: false`.
- No added row is promoted to a realized transaction merely because an eBay item page exists.
- No public page is treated as equivalent to authenticated eBay Product Research.
- Every canonical card has five labeled rows with at least two positive and two negative identity examples.
- Negatives deliberately stress grading, parallels, serial numbering, alternate inserts, and wrong-year/card identities.

The fixture is designed to make a passing matcher score harder to fake. The production matcher must still clear zero observed false accepts, >=99% precision, >=80% recall, and <=35% manual-review burden on this broader evidence set.

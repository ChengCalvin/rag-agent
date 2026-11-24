## Purpose

Gives the assistant live, read-only access to order information so it can report order status and decide return eligibility, combining current order data with documented policy.

## ADDED Requirements

### Requirement: Order status lookup
The assistant SHALL be able to retrieve the status of an order the caller is permitted to see, and SHALL report only the status-relevant fields: status, expected delivery, and ordered items.

#### Scenario: Permitted order
- **WHEN** an employee asks for the status of an order from their own store
- **THEN** the assistant reports its status, expected delivery and items

#### Scenario: Unknown order
- **WHEN** an employee asks about an order number that does not exist
- **THEN** the assistant says the order was not found or is not accessible

### Requirement: Order identifiers are validated
Order identifiers SHALL be validated against the defined format before any lookup. Malformed identifiers SHALL be rejected inside the order tool without querying order data; no earlier step (precheck, intake) SHALL reject or reroute them, so that a malformed identifier makes the same model calls as a nonexistent order.

#### Scenario: Malformed identifier
- **WHEN** an employee supplies an identifier that does not match the order number format
- **THEN** the assistant replies with the same not-found text used for nonexistent orders, with no follow-up question, and no order lookup occurs

#### Scenario: Malformed identifier costs the same as a nonexistent one
- **WHEN** an employee asks about a malformed identifier and then about an order that does not exist
- **THEN** both replies are the same code-produced text, make the same number of model calls and follow the same agent path, and no validator or composer runs

### Requirement: Return eligibility combines order data and policy
The system SHALL determine return eligibility from the order's delivery date, item category and condition together with the documented return policy, and the determination SHALL be computed deterministically, not by the language model. The assistant SHALL explain the outcome and cite the policy document.

#### Scenario: Within the return window
- **WHEN** an eligible item is within its return window
- **THEN** the assistant states it can be returned and cites the returns policy

#### Scenario: Category exception
- **WHEN** an item belongs to a category with a shorter window and the delivery date falls between the shorter and general windows
- **THEN** the assistant states it is not eligible and explains the category exception

#### Scenario: Policy cannot be determined
- **WHEN** the return policy parameters cannot be read
- **THEN** the assistant says it cannot determine eligibility and gives the escalation contact, in code-produced wording with no model-written text

### Requirement: Order tools are read-only
The assistant SHALL NOT have any capability to create, modify or cancel orders or customer records.

#### Scenario: Request to change an order
- **WHEN** an employee asks the assistant to cancel or modify an order
- **THEN** the assistant explains it can only look up information and points to the escalation path

### Requirement: Customer data is minimised
Tool output SHALL contain only the fields needed for the answer. Customer contact details SHALL be masked or omitted.

#### Scenario: Order lookup output
- **WHEN** an order is retrieved for an authorized caller
- **THEN** the result does not contain the customer's full address or full email address

### Requirement: Order questions skip the validation loop
A question about order status or return eligibility SHALL be answered on the order path directly: no policy search, no validator and no confidence band. The reply SHALL carry the label "From order records.", and a normal eligibility answer SHALL cite the policy document that its parameters come from.

#### Scenario: Order shortcut
- **WHEN** an employee asks for the status of an order they may see
- **THEN** the reply carries the label "From order records" and no confidence band, and no policy search or validator call is made

### Requirement: A message mixing order and policy parts is answered by the order path only
In this release a message that combines an order question with a free-text policy question SHALL be answered for its order part only, and the reply SHALL end with a fixed sentence, appended by code, that contains the words "cannot answer the policy part" and says the policy part should be asked separately.

#### Scenario: Combined question known limitation
- **WHEN** an employee asks for an order's status and, in the same message, for a general delivery policy
- **THEN** the order part is answered, no policy search is made, and the reply says it cannot answer the policy part


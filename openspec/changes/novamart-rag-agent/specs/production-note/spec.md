## Purpose

Explains to NovaMart how the prototype would become a production service on Google's enterprise stack, so the client can judge the approach, the risks and the open questions.

## ADDED Requirements

### Requirement: One-page production note
The project SHALL include a production note that fits on one page and covers: Gemini Enterprise versus a custom build, connecting the client's real data, security and governance, and evaluating and monitoring quality over time.

#### Scenario: Required topics present
- **WHEN** the note is read
- **THEN** each of the four topics has its own clearly labelled section

#### Scenario: Length limit
- **WHEN** the note is rendered to a page
- **THEN** it does not exceed one page

### Requirement: A reasoned build-versus-buy recommendation
The note SHALL give a recommendation on using Gemini Enterprise versus a custom agent, with the reasons and the conditions under which the recommendation would change.

#### Scenario: Recommendation stated
- **WHEN** the note is read
- **THEN** it states a recommended architecture, why it was chosen, and a fallback if a key assumption fails

### Requirement: Identity propagation is addressed
The note SHALL state how end-user identity reaches the order system so that store-level authorization is enforced by that system and not only by the agent, and SHALL identify this as an item to be confirmed early.

#### Scenario: Identity risk named
- **WHEN** the security section is read
- **THEN** it names the identity-propagation question, who must answer it, and the fallback

### Requirement: Claims about products are verified or flagged
Statements about specific Google product capabilities, names, limits or terms SHALL be checked against current official documentation before inclusion. Any statement not verified SHALL be marked as to be confirmed.

#### Scenario: Unverified claim
- **WHEN** a product capability could not be verified
- **THEN** the note marks it as to be confirmed rather than stating it as fact

### Requirement: Prototype limits are disclosed
The note SHALL state what the prototype simulates rather than implements, including identity and the order API.

#### Scenario: Limits section
- **WHEN** the note is read
- **THEN** it lists the simulated components and what replaces each in production

# Plan: Dynamic Role Test

## EPIC-000 - Bootstrap Dynamic Role

Roles: engineer
Objective: Create the 'security-auditor' role using the create-role skill template.
Working_dir: .

#### Definition of Done
- [ ] ~/.ostwin/roles/security-auditor/role.json created and valid
- [ ] ~/.ostwin/roles/security-auditor/ROLE.md created
- [ ] Registered in ~/.ostwin/roles/registry.json

## EPIC-001 - Create a hello world script

Roles: engineer
Objective: Create a simple hello.py script that prints "Hello from OS Twin" and a unit test to ensure >80% coverage.
Working_dir: .
Quality_gates: lint-clean, unit-tests

depends_on: [EPIC-000]

#### Definition of Done
- [ ] hello.py file created
- [ ] test_hello.py file created
- [ ] Script prints "Hello from OS Twin" when run
- [ ] Code coverage is at least 80%

#### Acceptance Criteria
- [ ] python3 hello.py outputs "Hello from OS Twin"
- [ ] pytest test_hello.py passes with coverage report

## EPIC-002 - Security review of hello script

Roles: security-auditor
Pipeline: security-auditor -> qa
Capabilities: security
Objective: Review hello.py for any security issues such as injection or unsafe inputs.
Working_dir: .
Quality_gates: security-scan-pass

depends_on: [EPIC-001]

#### Definition of Done
- [ ] Security review completed
- [ ] No critical vulnerabilities found
- [ ] Review verdict 'pass' accepted by QA
- [ ] Automated security scan (e.g., bandit) passes with zero issues

#### Acceptance Criteria
- [ ] Review report generated with pass or fail verdict
- [ ] QA signoff on the security report
- [ ] Security scan report confirms clean status

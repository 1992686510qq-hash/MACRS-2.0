# Claude-BugHunter Architecture Analysis

> Source: `github.com/elementalsouls/Claude-BugHunter` (mirror: `github.com/vishvacyber/Claude-Bughunter`)
> Author: Sachin Sharma (ElementalSoul)
> Analysis date: 2026-06-01

---

## 1. Executive Summary

Claude-BugHunter is a **drop-in skill bundle for Claude Code** that converts it from a general-purpose coding assistant into a specialized bug-hunting / red-team operator. It packs 51 SKILL.md modules, 15 slash commands, and 574+ disclosed-report vulnerability patterns across 24 vulnerability classes into a self-contained directory structure. The bundle is designed for **external attack surface only** (anything reachable from the internet), deliberately excluding internal AD, C2, post-exploit, evasion, and binary exploitation.

**Key differentiator**: It is not a tool that "does the hunting for you." It is a **cognitive framework** that teaches Claude Code how to think like a senior bug bounty hunter -- from methodology and mindset through detection, validation, and platform-specific reporting.

---

## 2. Vulnerability Classification: The 24 Categories

### 2.1 Complete Category Listing

The 24 vulnerability classes are organized into **7 functional groups**, each mapped to one or more `hunt-*` skills:

#### Group A: Injection & Client-Side (5 skills)

| Skill | Disclosed Reports | Core Techniques |
|-------|-------------------|-----------------|
| `hunt-xss` | 174 H1 reports | Reflected, DOM, stored, blind XSS; WAF bypass |
| `hunt-rce` | 67 H1 reports | Command injection, deserialization, file write to RCE |
| `hunt-sqli` | 8 H1 reports | Error/blind/time/UNION-based; second-order SQLi |
| `hunt-ssti` | Curated | Jinja2, Twig, Freemarker, ERB, Spring polyglot fuzzing |
| `hunt-xxe` | 4 H1 reports | In-band, OOB, DTD-parameter, XInclude, SVG injection |

#### Group B: Authorization & Authentication (5 skills)

| Skill | Disclosed Reports | Core Techniques |
|-------|-------------------|-----------------|
| `hunt-idor` | 26 H1 reports | 6 IDOR variants (numeric, UUID, indirect ref, param add, method swap, GraphQL node) |
| `hunt-auth-bypass` | 4 H1 reports | Header manipulation, verb switching, parameter pollution |
| `hunt-ato` | 9 ATO paths | User-enum + rate-limit + weak-password = ATO chains |
| `hunt-mfa-bypass` | 7 MFA patterns | 2FA bypass via response manipulation, OTP brute-force, session fixation |
| `hunt-csrf` | 10 H1 reports | State-changing endpoints, JSON CSRF, token stripping |

#### Group C: Identity Protocols (2 skills)

| Skill | Disclosed Reports | Core Techniques |
|-------|-------------------|-----------------|
| `hunt-oauth` | 10 H1 reports | redirect_uri abuse, state leakage, scope escalation, PKCE bypass |
| `hunt-saml` | Curated | XSW1-XSW8, XML Signature Wrapping, SSO chain attacks |

#### Group D: Server-Side Request & Response (4 skills)

| Skill | Disclosed Reports | Core Techniques |
|-------|-------------------|-----------------|
| `hunt-ssrf` | 9 H1 reports | 11 IP bypass techniques, cloud metadata chains (169.254.169.254), blind SSRF |
| `hunt-http-smuggling` | Curated | CL.TE, TE.CL, H2.CL, H2.TE request smuggling |
| `hunt-cache-poison` | 4 H1 reports | Unkeyed headers, fat GET, parameter cloaking |
| `hunt-jwt` | Curated | alg:none, RS256->HS256, kid injection, jku manipulation, JWKS spoofing |

#### Group E: API & Modern Stack (3 skills)

| Skill | Disclosed Reports | Core Techniques |
|-------|-------------------|-----------------|
| `hunt-api-misconfig` | Curated | Mass assignment, prototype pollution, CORS misconfig, JWT attacks |
| `hunt-graphql` | 3 H1 reports | Introspection abuse, depth-aliasing, batching bypass |
| `hunt-file-upload` | Curated | 10 bypass techniques: webshell, SVG XSS, DOCX XXE, path traversal, double extension |

#### Group F: Business Logic & Race Conditions (3 skills)

| Skill | Disclosed Reports | Core Techniques |
|-------|-------------------|-----------------|
| `hunt-business-logic` | 7 H1 reports | Coupon/pricing abuse, workflow bypass, negative quantity, integer overflow |
| `hunt-race-condition` | 3 H1 reports | TOCTOU, concurrent-request, limit-overrun, multi-step race |
| `hunt-llm-ai` | Curated | Prompt injection, ASCII smuggling, ASI01-AS10 framework |

#### Group G: Infrastructure, Misc & Catch-All (3 skills)

| Skill | Disclosed Reports | Core Techniques |
|-------|-------------------|-----------------|
| `hunt-cloud-misconfig` | Curated | Public S3, Lambda exposure, kubelet:10250, Docker:2375, IMDS chains |
| `hunt-subdomain` | 11 takeover patterns | 27+ provider fingerprints (AWS, Azure, GitHub Pages, etc.) |
| `hunt-misc` | 225 H1 reports | Clickjacking, open redirect, XS-leaks, CORS, info disclosure |

### 2.2 Taxonomy Structure

There is no strict hierarchical taxonomy tree (like CWE). Instead, the classification follows a **functional grouping** built around the question "What does the hunter need to know to find and exploit this class?" The group names reflect the attack surface dimension:

```
Level 0: Mode (Bug Bounty / Red Team / Pentest)
  |
  Level 1: Attack Surface Domain (Web App / Enterprise Platform / Cloud)
    |
    Level 2: Functional Group (Injection / Authorization / Identity / Server-Side / API / Business)
      |
      Level 3: Vulnerability Class (SQLi, XSS, IDOR, SSRF, etc.) -- 24 classes
        |
        Level 4: Variant / Technique (e.g., IDOR: numeric vs UUID vs GraphQL)
          |
          Level 5: Individual Disclosure Pattern (574+ total)
```

CWE mapping is **not built into the skills directly**. Bugcrowd VRT mapping exists in the `bugcrowd-reporting` skill for report submission purposes. Each `hunt-*` skill contains free-text root-cause descriptions and pattern libraries rather than CWE integer IDs.

---

## 3. Pattern Format: How 574+ Vulnerability Patterns Are Stored

### 3.1 Storage Mechanism

Patterns are **embedded directly inside each `hunt-*` skill's SKILL.md file** as Markdown-formatted knowledge. They are not in a separate database, JSON file, or vector store. Each SKILL.md bundles:

1. What to look for (detection signatures)
2. How to test it (step-by-step methodology)
3. What payloads to use (payload library with bypass variants)
4. How to chain it (primitive-to-impact escalation paths)
5. What real reports show (curated HackerOne report excerpts)

### 3.2 Pattern Template Structure

Each `hunt-*` SKILL.md follows this internal template:

```
1. VULNERABILITY SIGNATURE
   - HTTP request/response indicators
   - Parameter naming heuristics
   - Error message patterns
   - Technology fingerprinting clues

2. DETECTION WORKFLOW
   - Step-by-step testing procedure
   - Expected positive behavior
   - Expected negative behavior (control)
   - False positive discriminators

3. PAYLOAD LIBRARY
   - Basic detection payloads
   - Intermediate exploitation payloads
   - Advanced / WAF-bypass payloads
   - Protocol/stack-specific variants

4. BYPASS TABLE
   Filter Type | Bypass Technique | Payload
   WAF         | encoding         | %xx escape
   Input sanit | double encoding  | %2527
   ...

5. CHAIN TEMPLATES
   - "If you find X, try Y next"
   - Primitive -> Impact severity map
   - Multi-step attack path narratives

6. REAL-WORLD REFERENCES
   - Curated HackerOne report IDs
   - Key lessons from each disclosed report
   - Common causes of rejection
```

### 3.3 Pattern Density by Class

| Vulnerability Class | Pattern Count | Notes |
|---------------------|---------------|-------|
| hunt-misc | 225 | Catch-all: clickjacking, open redirect, XS-leaks, info disclosure |
| hunt-xss | 174 | All XSS variants (reflected, stored, DOM, blind) |
| hunt-rce | 67 | Command injection, deserialization, file-write chains |
| hunt-idor | 26 | All 6 variants across multiple platforms |
| hunt-subdomain / CSRF | 11 / 10 | Takeover patterns / CSRF on state-changing endpoints |
| hunt-ato / hunt-ssrf / OAuth | 9 each | ATO chains / SSRF bypasses / OAuth flows |
| hunt-sqli | 8 | Time, blind, error, UNION, second-order |
| hunt-business-logic / MFA | 7 each | Pricing/workflow abuse / 2FA bypass patterns |
| hunt-auth-bypass / cache-poison / XXE | 4 each | Header/verb/auth bypass / web cache / XML |
| hunt-graphql / race-condition | 3 each | Introspection/depth-aliasing / TOCTOU |
| Others (SSTI, SAML, JWT, smuggling, etc.) | Curated | Focus on technique depth over pattern count |

### 3.4 Pattern Quality Assessment

**Strengths:**
- Rooted in **real disclosed HackerOne reports** -- not synthetic or textbook examples
- Each pattern includes the **full detection-to-report chain**, not just a payload list
- **Bypass tables** are specific and actionable (exact payloads for each filter type)
- **Chain templates** show how to escalate primitives to Critical severity

**Weaknesses:**
- No structured machine-readable format (no JSON/YAML schema, no CWE IDs)
- No CVSS or severity scoring within patterns (severity is handled by the triage gate)
- Patterns are free-text Markdown -- not queryable or searchable across classes
- No cross-class indexing (e.g., "which patterns involve SQL injection + authorization bypass?")
- Dense text format means LLM context window consumption is significant per skill load

---

## 4. Skill Architecture: 51 Skills vs 15 Slash Commands

### 4.1 Two-Tier Invocation Model

The bundle exposes **two interfaces** with different audiences:

| Property | Slash Commands (15) | SKILL.md Files (51) |
|----------|---------------------|---------------------|
| **Interface** | `/command` typed by user | Auto-loaded by keyword |
| **Invocation** | Explicit: user types `/hunt` | Implicit: Claude detects relevant keywords |
| **Granularity** | Workflow-level (Phase) | Vulnerability-class-level (Technique) |
| **Who triggers** | Human operator | Claude Code itself |
| **Example** | `/recon target.com` | User says "testing JWT tokens" -> loads `hunt-jwt` |

### 4.2 Slash Command to Skill Mapping

| Slash Command | Phase | Skills Invoked | Purpose |
|---------------|-------|----------------|---------|
| `/scope` | PHASE 1 | `bug-bounty`, `bb-methodology` | Set engagement scope, scaffold folder |
| `/surface` | PHASE 1 | `web2-recon`, `offensive-osint` | Map attack surface |
| `/recon` | PHASE 2 | `offensive-osint`, `web2-recon`, `osint-methodology` | Subdomain enum, endpoint map, JS harvest |
| `/intel` | PHASE 2 | `osint-methodology` | Intelligence gathering |
| `/hunt` | PHASE 3 | `hunt-dispatch` -> 1+ `hunt-*` skills | Hunt for vulnerabilities |
| `/chain` | PHASE 3 | Cross-skill chain templates | Chain primitives into attack paths |
| `/triage` | PHASE 4 | `triage-validation` | 7-Question Gate validation |
| `/validate` | PHASE 4 | `triage-validation` | Second-pass validation |
| `/report` | PHASE 6 | `report-writing`, `bugcrowd-reporting` | Generate platform-specific report |
| `/autopilot` | ALL | Full pipeline router | Automated end-to-end workflow |
| `/pickup` | ANY | State restoration | Resume previous engagement |
| `/remember` | POST-SUBMIT | State persistence | Persist submission UUIDs |
| `/memory-gc` | MAINTENANCE | Memory management | Clear stale context |
| `/token-scan` | RECON | Token detection patterns | Scan for exposed tokens/secrets |
| `/web3-audit` | SPECIALIZED | `web3-audit` | Smart contract audit mode |

### 4.3 Skill Auto-Loading Mechanism

The auto-loading is keyword-based. Claude Code monitors the conversation, and when the user describes their testing target in plain English, the relevant skills load automatically:

| User says (plain English) | Skill(s) auto-loaded |
|---------------------------|----------------------|
| "I'm looking at a file upload form" | `hunt-file-upload` |
| "Okta tenant" | `okta-attack` |
| "This S3 bucket is public" | `hunt-cloud-misconfig` |
| "They use JWT for auth" | `hunt-jwt` |
| "Business logic on the checkout page" | `hunt-business-logic` |
| "Entra ID tenant" | `m365-entra-attack` |

This is achieved through Claude Code's native SKILL.md discovery mechanism -- the `skills/` directory is scanned at startup, and each SKILL.md's frontmatter metadata (name, description, keywords) determines when it activates.

### 4.4 Secondary Interface: `cbh` CLI

A Python-based CLI (`cbh`) provides a deterministic, non-LLM alternative for CI/CD and scripted use:

```
cbh recon <target>     # Scripted recon (regex + network I/O)
cbh classify <finding> # Deterministic vulnerability classification
cbh triage <finding>   # 7-question gate without LLM overhead
cbh report <finding>   # Template-based report generation
```

This dual-interface design means the pattern knowledge is accessible outside of Claude Code conversations.

### 4.5 The 7 Capability Domains (51-Skill Organization)

| # | Domain | Skill Count | Names |
|---|--------|-------------|-------|
| 1 | Scope & Methodology | 3 | `bug-bounty`, `bb-methodology`, `bb-local-toolkit` |
| 2 | Recon & OSINT | 3 | `offensive-osint`, `web2-recon`, `osint-methodology` |
| 3 | Hunt -- Web App | 27 | All `hunt-*` skills covering 24 vulnerability classes |
| 4 | Enterprise Platform Attack | 10 | `m365-entra-attack`, `okta-attack`, `cloud-iam-deep`, `vmware-vcenter-attack`, `enterprise-vpn-attack`, `hunt-sharepoint`, `hunt-aspnet`, `hunt-ntlm-info`, `apk-redteam-pipeline`, `supply-chain-attack-recon` |
| 5 | Red Team Tradecraft | 2 | `redteam-mindset`, `mid-engagement-ir-detection` |
| 6 | Validation | 2 | `triage-validation`, `hunt-dispatch` |
| 7 | Reporting & Hygiene | 4 | `evidence-hygiene`, `report-writing`, `bugcrowd-reporting`, `redteam-report-template` |

### 4.6 File Tree Structure

```
Claude-BugHunter/
├── skills/                                  # 51 SKILL.md bundles
│   ├── apk-redteam-pipeline/                # APK -> jadx -> secrets -> Frida
│   ├── bb-local-toolkit/                    # Full bug-bounty workflow pipeline router
│   ├── bb-methodology/                      # 5-phase non-linear hunting workflow
│   ├── bug-bounty/                          # Master orchestrator (vendored)
│   ├── bugcrowd-reporting/                  # VRT, OOS rebuttals, severity requests
│   ├── cloud-iam-deep/                      # AWS/Azure/GCP IAM priv-esc chains
│   ├── enterprise-vpn-attack/               # Cisco/Fortinet/Citrix/PAN/Pulse SSL VPN
│   ├── evidence-hygiene/                    # Cookie/PII/HAR redaction discipline
│   ├── hunt-api-misconfig/                  # Mass assignment, JWT, prototype pollution, CORS
│   ├── hunt-aspnet/                         # ASP.NET ViewState, machineKey, WebForms
│   ├── hunt-ato/                            # 9 account-takeover paths + chains
│   ├── hunt-auth-bypass/                    # Auth bypass -- 4 disclosed reports
│   ├── hunt-business-logic/                 # Business logic flaws -- 7 disclosed reports
│   ├── hunt-cache-poison/                   # Cache poisoning -- 4 disclosed reports
│   ├── hunt-cloud-misconfig/                # S3, Lambda, RDS, IAM-in-JS, metadata SSRF
│   ├── hunt-csrf/                           # CSRF -- 10 disclosed reports
│   ├── hunt-dispatch/                       # /hunt mode router (redteam vs WAPT)
│   ├── hunt-file-upload/                    # Webshell, SVG XSS, DOCX XXE, traversal
│   ├── hunt-graphql/                        # GraphQL -- 3 disclosed reports
│   ├── hunt-http-smuggling/                 # CL.TE / TE.CL request smuggling
│   ├── hunt-idor/                           # IDOR -- 26 disclosed reports
│   ├── hunt-llm-ai/                         # Prompt injection, ASCII smuggling, ASI01-10
│   ├── hunt-mfa-bypass/                     # 7 MFA/2FA bypass patterns
│   ├── hunt-misc/                           # Catch-all -- 225 disclosed reports
│   ├── hunt-ntlm-info/                      # NTLM Type-2 AD topology disclosure
│   ├── hunt-oauth/                          # OAuth -- 10 disclosed reports
│   ├── hunt-race-condition/                 # Race conditions -- 3 disclosed reports
│   ├── hunt-rce/                            # RCE -- 67 disclosed reports
│   ├── hunt-saml/                           # SAML XSW1-XSW8 + SSO attacks
│   ├── hunt-sharepoint/                     # SharePoint on-prem (ToolShell, anon SOAP)
│   ├── hunt-sqli/                           # SQLi -- 8 disclosed reports
│   ├── hunt-ssrf/                           # SSRF -- 9 disclosed reports
│   ├── hunt-ssti/                           # SSTI -- polyglot fuzzing
│   ├── hunt-xss/                            # XSS -- reflected, stored, DOM, blind
│   ├── hunt-xxe/                            # XXE -- in-band, OOB, SVG, DOCX
│   ├── m365-entra-attack/                   # Microsoft 365 / Entra ID attack matrix
│   ├── mid-engagement-ir-detection/         # SOC-patch & baseline-shift detection
│   ├── offensive-osint/                     # 15-ref probe arsenal
│   ├── okta-attack/                         # Okta attack surface
│   ├── osint-methodology/                   # 5-stage OSINT pipeline
│   ├── redteam-mindset/                     # Operator discipline
│   ├── redteam-report-template/             # DOCX deliverable template
│   ├── report-writing/                      # H1 / Intigriti / Immunefi templates
│   ├── supply-chain-attack-recon/           # Supply chain recon
│   ├── triage-validation/                   # 7-Question Gate (PASS/DOWNGRADE/KILL/CHAIN)
│   ├── vmware-vcenter-attack/               # vCenter attack surface
│   ├── web2-recon/                          # Subdomain + endpoint enumeration
│   └── web3-audit/                          # Web3/smart-contract audit skill
│
├── commands/                                # 15 slash commands
│   ├── /autopilot /chain /hunt /intel /memory-gc /pickup
│   ├── /recon /remember /report /scope /surface
│   ├── /token-scan /triage /validate /web3-audit
│
├── docs/                                    # Documentation
├── cbh CLI                                  # CLI tool: recon / classify / triage / report
└── Burp MCP integration                     # Burp Suite MCP connector
```

---

## 5. Enterprise Identity + Infrastructure Attack Matrix

### 5.1 Matrix Structure

The "Platform Attack" layer (Layer 3 of the 4-layer architecture) contains 10 enterprise-focused skills forming a comprehensive attack matrix across identity fabric, cloud IAM, virtualization, and perimeter appliances.

### 5.2 Identity Fabric Attacks

**`m365-entra-attack`**: Microsoft 365 / Entra ID attack chains
- AADSTS error code references for tenant fingerprinting
- Conditional Access policy inferencing from error codes
- OAuth consent grant phishing chains
- Device-code authentication phishing
- Service principal abuse and managed identity pivoting
- STS chaining (Azure -> on-prem AD CS)

**`okta-attack`**: Okta-as-IdP attack chains
- Okta tenant discovery
- SAML/OIDC misconfiguration in enterprise contexts
- Okta API token exposure paths
- Cross-tenant trust abuse

### 5.3 Cloud IAM Escalation

**`cloud-iam-deep`**: Multi-cloud IAM privilege escalation
- AWS: 24+ escalation paths (IAM role chaining, STS AssumeRole, instance profile abuse)
- Azure: 8+ paths (managed identity, RBAC, resource hierarchy traversal)
- GCP: 6+ paths (service account impersonation, workload identity federation)
- Cross-cloud STS / identity federation confused deputy
- IMDS v1/v2 exploitation
- K8s service account token theft -> cloud credential extraction

### 5.4 Virtualization & Perimeter

**`vmware-vcenter-attack`**: Virtualization platform attack
- vCenter SSO domain extraction
- Workspace ONE / Horizon attack surface
- Version fingerprinting and CVE matching

**`enterprise-vpn-attack`**: SSL VPN appliances
- Cisco AnyConnect, Fortinet FortiGate VPN, Citrix ADC/Netscaler, Palo Alto GlobalProtect, Pulse Secure, SonicWall, F5 BIG-IP
- Currently-referenced CVE chains (2024-2026)
- Pre-auth attack surface mapping
- Post-auth lateral movement paths

### 5.5 SharePoint Ecosystem

**`hunt-sharepoint`**: SharePoint on-prem -- ToolShell, legacy SOAP, anonymous endpoints, ViewState
**`hunt-aspnet`**: ASP.NET -- machineKey decryption, WebForms event validation bypass, ViewState MAC bypass
**`hunt-ntlm-info`**: NTLM Type-2 relay -- AD topology disclosure, internal naming convention recovery

### 5.6 Mobile & Supply Chain

**`apk-redteam-pipeline`**: Android APK acquisition -> jadx -> secrets extraction -> Frida hooking
**`supply-chain-attack-recon`**: Dependency confusion, package registry squatting, CI/CD pipeline exposure mapping

### 5.7 Matrix Quality Assessment

**Strengths:**
- Covers current (2024-2026) CVEs, not stale content
- AADSTS error code matrix for Entra ID is a unique, high-value asset
- Post-credential paths cover what happens after you get in
- Cross-platform (M365 + Okta + AWS + Azure + GCP + on-prem)

**Weaknesses:**
- No internal AD attacks (Kerberoasting, DCSync, BloodHound) -- acknowledged as "future bundle"
- No zero-day hunting methodology -- CVE-focused
- VMware/SharePoint content depth unclear
- No on-prem Exchange / hybrid identity focused content

---

## 6. The 6-Phase Engagement Workflow

```
PHASE 0: MODE SELECTION
  ├── Bug Bounty -> standard flow
  ├── Red Team   -> + redteam-mindset + mid-engagement-ir-detection
  └── Pentest    -> standard flow (WAPT)

PHASE 1: SCOPE  [/scope command]
  └── Scaffold engagement folder: CLAUDE.md, scope.md, findings/, evidence/

PHASE 2: RECON  [/recon, /intel, /token-scan commands]
  └── Subdomain enum -> endpoint map -> JS harvest -> identity fabric mapping

PHASE 3: HUNT  [/hunt, /chain commands]
  ├── Hypothesis-driven testing against pattern libraries
  ├── 27 hunt-* skills auto-load by keyword
  └── Loop here until lead found

PHASE 4: VALIDATE  [/triage, /validate commands]
  └── 7-Question Gate (MANDATORY):
      Q1: Attacker exploitable right now with real HTTP request?
      Q2: Impact on accepted-impact list?
      Q3: Asset in scope?
      Q4: No admin-only assumption?
      Q5: Not already known/documented?
      Q6: Concrete impact, not "technically possible"?
      Q7: Not on never-submit list?

      Verdicts:
      PASS (all 7 yes)         -> PHASE 5
      DOWNGRADE (Q2/Q5 fail)   -> PHASE 5 (lower severity)
      CHAIN REQUIRED           -> PHASE 3 (find companion primitive)
      KILL (any other fail)    -> PHASE 3 (kill lead, keep hunting)

PHASE 5: CAPTURE
  └── Cookie redaction, PII black-bar, HAR sanitization, screenshot ordering

PHASE 6: REPORT  [/report command]
  └── H1 / Bugcrowd VRT / Intigriti / Immunefi template generation

SUBMIT -> Append UUID -> /remember -> Cross-reference -> Loop to PHASE 3
```

---

## 7. Integration Surface: Code Security Review Sub-Agent

### 7.1 How It Could Be Used

Claude-BugHunter is designed as a **runtime/black-box hunting** tool, not a SAST/static analysis tool. However, its pattern libraries are directly applicable to code security review in several ways:

**1. Pattern-Based Code Grep (most straightforward)**
Each `hunt-*` skill contains grep/ripgrep patterns for finding vulnerable code patterns:
- `hunt-sqli`: `grep -rn "execute\\|executemany\\|raw(" --include="*.py" | grep -v "?"` finds unparameterized queries
- `hunt-idor`: `grep "SELECT.*WHERE.*id = ?"` with no `AND user_id = ?` clause
- `hunt-xss`: `grep -rn "innerHTML\\|document.write\\|dangerouslySetInnerHTML" --include="*.js"`
- These patterns can be extracted and used in a code review sub-agent

**2. Triage Gate as Review Filter**
The 7-Question Gate can be adapted for code review findings:
- "Is this code path reachable from an unauthenticated endpoint?" (equivalent to Q1)
- "Does this bug actually result in data leakage or code execution?" (equivalent to Q6)
- "Is this just the documented API behavior?" (equivalent to Q5)

**3. Enterprise Attack Matrix for Infrastructure-as-Code Review**
The cloud IAM, Okta, and M365 attack skills could be adapted to review Terraform/CloudFormation/Bicep for misconfigurations matching known attack patterns.

### 7.2 Prompt for a Code Security Review Sub-Agent

```markdown
You are a code security reviewer powered by Claude-BugHunter vulnerability patterns.
You analyze pull requests for security vulnerabilities using curated detection
patterns from 574+ disclosed HackerOne reports across 24 vulnerability classes.

## Review Methodology
For each file in the PR diff:
1. CLASSIFY the code context (auth flow, data access, input handling, API endpoint, config)
2. MATCH against the relevant vulnerability class patterns from the knowledge base
3. TEST with grep patterns: look for known-dangerous constructs
4. TRIAGE using adapted 7-Question Gate:
   Q1: Is this code path reachable from external input without auth?
   Q2: Does the vulnerability have concrete data/execution impact?
   Q3: Is this in the changed code (in scope)?
   Q4: Is this exploitable by a user who doesn't have admin access?
   Q5: Is this not already documented as intentional behavior?
   Q6: Can you prove impact beyond "this looks wrong"?
   Q7: Is this not a known/acknowledged risk?

Output format:
{
  "finding_id": "BH-001",
  "class": "SQL Injection",
  "file": "src/auth/login.py",
  "line": 42,
  "pattern_match": "execute() with string formatting, no parameterization",
  "exploit_chain": "Login form username -> SQLi -> user table exfiltration",
  "severity": "Critical",
  "remediation": "Replace string formatting with parameterized query",
  "h1_reference": "H1 report #XXXXXX (similar pattern)"
}

If no vulnerabilities found, report "NO_VULNERABILITIES" with confidence level.
```

### 7.3 Integration Architecture Options

```
Option A: Embed patterns directly in sub-agent prompt
  Pro: Simple, no infrastructure
  Con: Token-heavy (~100K tokens for all patterns), need subset selection

Option B: RAG-style pattern retrieval
  Pro: Only load patterns relevant to code context
  Con: Requires vector store + retrieval pipeline

Option C: Hybrid -- load hunt-dispatch skill + grep patterns
  Pro: Lightweight (<5K tokens), uses bundle's own dispatch logic
  Con: Less thorough than full pattern set
```

---

## 8. Knowledge Base Reusability Assessment

### 8.1 Can the 574+ Patterns Be Extracted as a Standalone Knowledge Base?

**YES, with effort.** The patterns are embedded in SKILL.md files as structured Markdown. They could be extracted into:

| Target Format | Effort | Utility |
|---------------|--------|---------|
| JSON/YAML pattern catalog | Medium | Direct use in other review systems |
| Vector embeddings for RAG | Medium | Semantic search across vulnerability classes |
| CWE-mapped database | High | Interoperability with SAST tools |
| Sigma/YARA-style rules | Low-Medium | Detect patterns in HTTP traffic / code |
| Custom Claude skills | Low | Already in Claude Code skill format |

### 8.2 Extraction Effort Breakdown

**Easy (hours):**
- Parse each `hunt-*` SKILL.md to extract grep patterns into a flat file
- Extract payloads into categorized wordlists
- Extract bypass tables into structured CSV

**Medium (days):**
- Build a JSON schema for the pattern format and parse all 51 SKILL.md files
- Map each pattern to CWE IDs (requires manual review)
- Build cross-class indices (e.g., "all patterns involving JWTs")

**Hard (weeks):**
- Build a complete CWE taxonomy mapping with parent-child relationships
- Normalize all patterns into a unified machine-readable schema
- Build a CLI or API for pattern query and retrieval

### 8.3 License Consideration

The repository is open-source on GitHub. The README does not explicitly state a license, so reuse for commercial purposes may have restrictions. Check the actual LICENSE file before extracting for production use.

---

## 9. Strengths & Weaknesses

### 9.1 Strengths

| # | Strength | Impact |
|---|----------|--------|
| 1 | **Rooted in real disclosed reports** (not textbooks) | Patterns reflect what actually works in the wild |
| 2 | **7-Question Gate is a Force Multiplier** | Saves hours per finding by filtering false positives before report writing |
| 3 | **CHAIN REQUIRED verdict** | Recognizes that many findings only become Critical in combination -- prevents premature reporting |
| 4 | **Enterprise identity fabric coverage** | M365/Entra + Okta + cloud IAM is a unique asset rarely found in bug bounty tools |
| 5 | **CVE relevance (2024-2026)** | Maintained against current threats, not stale |
| 6 | **Cognitive framework, not just payload list** | Teaches "how to think" (methodology, mindset), not just "what to type" |
| 7 | **Auto-loading by keyword** | No manual skill invocation -- describe target, skill loads automatically |
| 8 | **Dual interface (slash + CLI)** | Works both in Claude Code and in automation pipelines |
| 9 | **Platform-specific reporting** | H1, Bugcrowd VRT, Intigriti, Immunefi -- each with correct format |
| 10 | **Clear scope boundaries** | Explicitly states what is OUT of scope (avoids hallucination into unsupported areas) |
| 11 | **Evidence hygiene discipline** | Built-in PII/cookie redaction prevents accidental data leaks in reports |
| 12 | **Red team mindset overlay** | "DO NOT STOP" directive + IR detection for red team engagements |

### 9.2 Weaknesses

| # | Weakness | Impact | Mitigation |
|---|----------|--------|------------|
| 1 | **No structured pattern schema** | Patterns are free-text Markdown, not queryable or cross-referenced | Build JSON extraction layer |
| 2 | **No CWE mapping** | Cannot interoperate with SAST tools or vulnerability management systems | Manual mapping effort |
| 3 | **No CVSS scoring** | Severity is handled qualitatively by triage gate, not quantitatively | Add CVSS v3.1 calculator to triage skill |
| 4 | **Dense SKILL.md files** | Loading full skill consumes significant LLM context window | Progressive disclosure already built in, but still large per-skill |
| 5 | **Black-box focus** | Designed for runtime testing, lacks source code review methodology | Grep patterns exist but not systematized |
| 6 | **No internal AD attacks** | Kerberoasting, DCSync, BloodHound excluded (future bundle) | Acknowledge gap, wait for v2 |
| 7 | **No zero-day methodology** | CVE-focused for enterprise platforms, not novel vulnerability research | Add fuzzing/differential analysis skills |
| 8 | **No DAST/scan automation** | Relies on human hypothesis-driven testing, not automated scanning | Combine with existing DAST tools |
| 9 | **No false-positive feedback loop** | Triage gate filters one finding at a time; no learning from bulk results | Add pattern effectiveness tracking |
| 10 | **Single-author maintenance** | Bus factor of 1; if Sachin Sharma stops updating, CVEs go stale | Community contribution pipeline |
| 11 | **No formal verification** | Patterns claim to be from H1 reports but aren't independently verified | Cross-reference with CVE databases |
| 12 | **Context window contention** | 51 skills at metadata level is fine (~100 tokens each = 5.1K), but loading 5+ full skills simultaneously strains windows | Need smarter skill subset selection |

### 9.3 What's Missing for Production Code Review Use

If adapting Claude-BugHunter for **automated code security review** (as opposed to manual bug hunting), these would need to be added:

1. **SAST pattern format**: Convert HTTP-based patterns to code pattern matching
2. **Language-specific detection rules**: Current patterns are protocol-level; need Python/JS/Java/Go/C# rule sets
3. **False positive rate metrics**: No data on precision/recall for automated scanning
4. **CI/CD integration**: No GitHub Actions / GitLab CI pipeline support
5. **Severity consistency**: Qualitative triage gate vs quantitative CVSS for automation
6. **Remediation guidance**: Patterns focus on exploitation, not fix recommendations
7. **OWASP Top 10 / CWE Top 25 mapping**: For compliance reporting
8. **Batch review mode**: Current flow is one finding at a time (human-paced)

---

## 10. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CLAUDE-BUGHUNTER                              │
│                     Claude Code Skill Bundle                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────── INTERFACES ──────────────────────────┐     │
│  │                                                              │     │
│  │  SLASH COMMANDS (15)           cbh CLI (secondary)          │     │
│  │  /recon /hunt /triage          cbh recon                    │     │
│  │  /report /chain /autopilot     cbh classify                 │     │
│  │  /scope /surface /pickup       cbh triage                   │     │
│  │  /intel /remember /memory-gc   cbh report                   │     │
│  │  /token-scan /web3-audit                                    │     │
│  │  /validate                                                   │     │
│  └──────────────────────┬──────────────────────────────────────┘     │
│                         │                                            │
│  ┌──────────────────────┴──────────────────────────────────────┐     │
│  │                    SKILL DISPATCH                             │     │
│  │  Keyword auto-loading + hunt-dispatch router                 │     │
│  └──────────────────────┬──────────────────────────────────────┘     │
│                         │                                            │
│  ┌──────────────────────┴──────────────────────────────────────┐     │
│  │                 4-LAYER SKILL STACK                          │     │
│  │                                                              │     │
│  │  L1: METHODOLOGY (3 skills)                                  │     │
│  │  bug-bounty + bb-methodology + redteam-mindset               │     │
│  │                                                              │     │
│  │  L2: WEB APP HUNTING (27 skills)                             │     │
│  │  24 vulnerability classes × 574+ disclosed-report patterns   │     │
│  │  │ Injection (5) │ Authorization (5) │ Identity (2) │        │     │
│  │  │ Server-Side (4)│ API/Modern (3)    │ Business (3)│        │     │
│  │  │ Infrastructure (3) │ Catch-All (1)              │        │     │
│  │                                                              │     │
│  │  L3: ENTERPRISE ATTACK MATRIX (10 skills)                    │     │
│  │  M365/Entra │ Okta │ Cloud IAM │ vCenter │ VPN │ SharePoint │     │
│  │  ASP.NET │ NTLM │ APK Pipeline │ Supply Chain               │     │
│  │                                                              │     │
│  │  L4: REPORTING & VALIDATION (6 skills)                       │     │
│  │  Triage Gate │ Evidence Hygiene │ Multi-Platform Reports     │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  ENGAGEMENT PIPELINE                                                 │
│  MODE -> SCOPE -> RECON -> HUNT -> VALIDATE -> CAPTURE -> REPORT     │
│                              ↑↓                      ↑↓              │
│                         CHAIN LOOP             DOWNGRADE PATH         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 11. Recommendations for Xun-CC-Panel Integration

### 11.1 If Using Claude-BugHunter as a Code Review Sub-Agent:

1. **Start with grep pattern extraction**: Pull all grep/rg detection patterns from the 27 `hunt-*` skills into a single patterns file. This gives immediate code review value with minimal effort.

2. **Adapt the 7-Question Gate for code context**: Rewrite the triage questions for source code review (reachability, impact, scope).

3. **Subset selection by file type**: Use `hunt-dispatch` skill's classification logic to select which vulnerability classes to load based on the code being reviewed (Python = SQLi + SSTI + RCE; JavaScript = XSS + prototype pollution; Terraform = cloud misconfig).

4. **Add language-specific rules**: Current patterns are HTTP/protocol level. Supplement with language-specific SAST rules for Python, JavaScript, Java, Go.

5. **Build pattern-to-CWE bridge**: Map the 24 classes to CWE IDs for interoperability with existing SAST tools.

### 11.2 Quick Wins:

- Extract all 574+ patterns' grep signatures into a `patterns/grep-signatures.txt` file
- Extract all payloads into categorized wordlists in `payloads/`
- Build a `CLAUDE.md` that loads `bug-bounty` + `triage-validation` as the base, then dispatches `hunt-*` skills based on code context
- Use `evidence-hygiene` skill for automatic report sanitization

### 11.3 Risks:

- Patterns are HTTP/runtime focused; directly adapting to code review may miss logic bugs visible only at runtime
- No training data on false-positive rates in code review context
- Enterprise attack matrix skills assume runtime access (not applicable to static code review of non-infra code)

---

## 12. Sources

- Primary repository: `github.com/elementalsouls/Claude-BugHunter`
- Mirror: `github.com/vishvacyber/Claude-Bughunter`
- Blog walkthrough: [Claude-BugHunter: The Open-Source AI Security Agent](https://osintteam.blog/claude-bughunter-the-open-source-ai-security-agent-that-turns-claude-code-into-a-bug-bounty-b480582a6925)
- DeepWiki reference: [Security Skills Library](https://deepwiki.com/zebbern/claude-code-guide/10.5-security-skills-library)
- Korean community review: [PyTorchKR discussion](https://discuss.pytorch.kr/t/claude-bughunter-51-claude-code/10390)

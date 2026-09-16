---
name: security_assurance
description: Realiza aseguramiento profesional de aplicaciones siguiendo OWASP Top 10, normas de seguridad informática y buenas prácticas DevSecOps. Detecta vulnerabilidades, propone correcciones y genera reportes ejecutivos. Use ONLY when analyzing code/config for security vulnerabilities, compliance audits, or DevSecOps reviews.
author: Haymer Barbetti Andrade
version: 1.0.0
tags: [security, owasp, devsecops, compliance, audit]
---

# Security Assurance Skill

## Purpose
Professional application security assurance following OWASP Top 10, security standards, and DevSecOps best practices. Detects vulnerabilities, proposes fixes, and generates executive reports.

## Inputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `source_code` | text | Source code or fragment to analyze |
| `language` | text | Programming language (Java, Go, Python, JS, etc.) |
| `framework` | text | Framework used (Spring, Express, Django, FastAPI, etc.) |
| `config_files` | text | Deployment configs (Dockerfile, YAML, .env, docker-compose.yml) |
| `compliance_standard` | text | Reference standard (OWASP, ISO 27001, NIST, PCI-DSS) |

## Outputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `vulnerabilities` | json | List of detected vulnerabilities with risk level |
| `recommendations` | text | Fix and mitigation suggestions |
| `compliance_report` | text | Compliance status against chosen standard |

## Workflow Steps

### 1. Analyze Code (`analyze_code`)
Scans code for OWASP Top 10 vulnerabilities and insecure patterns.

**Common vulnerability patterns to detect:**
- **A01: Broken Access Control** - Missing authz checks, IDOR, path traversal
- **A02: Cryptographic Failures** - Weak crypto, hardcoded secrets, plaintext sensitive data
- **A03: Injection** - SQLi, NoSQLi, command injection, LDAP injection, XSS
- **A04: Insecure Design** - Missing threat modeling, insecure defaults
- **A05: Security Misconfiguration** - Default creds, exposed debug, unnecessary features
- **A06: Vulnerable Components** - Outdated deps, unpatched CVEs
- **A07: Auth Failures** - Weak passwords, session fixation, missing MFA
- **A08: Software/Data Integrity** - Unsigned updates, CI/CD tampering
- **A09: Logging/Monitoring Failures** - Insufficient logs, no alerting
- **A10: SSRF** - Unvalidated user-supplied URLs

**Language-specific checks:**
- Python: `eval/exec`, `pickle`, `subprocess.shell=True`, SQL string formatting
- JavaScript/Node: `eval`, `innerHTML`, `child_process`, prototype pollution
- Go: `exec.Command` with user input, template injection
- Java: Deserialization, XXE, JNDI injection

### 2. Analyze Config (`analyze_config`)
Evaluates deployment, container, and secret configurations.

**Docker/Container checks:**
- Running as root (`USER root` or missing `USER`)
- `--privileged`, `--cap-add=ALL`
- Exposed sensitive ports
- Hardcoded secrets in images
- Base image vulnerabilities (use distroless/alpine)
- Missing `HEALTHCHECK`
- No resource limits (CPU/memory)

**Kubernetes/YAML checks:**
- `privileged: true`, `allowPrivilegeEscalation: true`
- Missing `securityContext` (runAsNonRoot, readOnlyRootFilesystem)
- Secrets in ConfigMaps instead of Secrets
- Missing network policies
- Default service accounts with excessive permissions

**Environment/Secrets:**
- `.env` committed to git
- Secrets in code/comments
- Weak JWT secrets
- API keys in frontend bundles

### 3. Compliance Check (`compliance_check`)
Verifies compliance with selected standard.

**OWASP ASVS (Application Security Verification Standard):**
- Level 1: Basic security requirements
- Level 2: Standard for most apps
- Level 3: High-value/high-risk apps

**ISO 27001 Annex A controls mapping:**
- A.5: Information security policies
- A.6: Organization of information security
- A.8: Asset management
- A.9: Access control
- A.12: Operations security
- A.14: System acquisition/development

**NIST CSF Functions:**
- Identify, Protect, Detect, Respond, Recover

**PCI-DSS (if handling payments):**
- Req 1-12: Network, cardholder data, vulnerability mgmt, access control, monitoring, policy

### 4. Generate Report (`generate_report`)
Creates executive report with findings.

**Report structure:**
```markdown
# Security Assessment Report

## Executive Summary
- Overall risk rating: CRITICAL/HIGH/MEDIUM/LOW
- Total findings: X (Critical: Y, High: Z, Medium: W, Low: V)
- Compliance status: PASS/FAIL/PARTIAL

## Vulnerabilities
| ID | Title | OWASP Category | Severity | Location | Description | Impact | Remediation |
|----|-------|----------------|----------|----------|-------------|--------|-------------|

## Configuration Issues
| ID | Component | Issue | Severity | Recommendation |

## Compliance Matrix
| Control | Standard | Status | Evidence | Gap |

## Recommendations Priority
1. **Immediate (0-24h)**: Critical vulnerabilities
2. **Short-term (1-7 days)**: High severity
3. **Medium-term (1-4 weeks)**: Medium severity
4. **Long-term (1-3 months)**: Low severity, hardening

## DevSecOps Integration
- SAST/DAST tool recommendations
- CI/CD pipeline security gates
- Dependency scanning automation
- Secret scanning in pre-commit
```

## Usage Examples

### Analyze Python FastAPI backend
```bash
# Provide source code and config for analysis
security_assurance:
  source_code: "backend/main.py + backend/auth.py + backend/database.py"
  language: "Python"
  framework: "FastAPI"
  config_files: "Dockerfile + docker-compose.yml + .env.example"
  compliance_standard: "OWASP"
```

### Analyze React frontend
```bash
security_assurance:
  source_code: "frontend/src/"
  language: "JavaScript"
  framework: "React + Vite"
  config_files: "frontend/Dockerfile + frontend/nginx.conf"
  compliance_standard: "OWASP"
```

### Full stack audit
```bash
security_assurance:
  source_code: "Complete codebase"
  language: "Python, JavaScript"
  framework: "FastAPI, React"
  config_files: "All Docker, compose, nginx, .env files"
  compliance_standard: "ISO 27001"
```

## Integration Notes
- Run as part of CI/CD pipeline (pre-merge gate)
- Schedule weekly automated scans
- Integrate with GitHub/GitLab security advisories
- Use with `trivy`, `semgrep`, `bandit`, `eslint-security`, `snyk`
- Output feeds into vulnerability management system
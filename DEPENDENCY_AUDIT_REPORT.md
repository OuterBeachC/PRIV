# Dependency Audit Report
**Date:** 2026-01-13
**Project:** PRIV Financial Holdings Dashboard
**Auditor:** Claude Code

---

## Executive Summary

This report presents findings from a comprehensive dependency audit of the PRIV project, including security vulnerabilities, outdated packages, code-level security issues, and unnecessary bloat.

### Critical Findings
- ❌ No requirements.txt file existed (✅ now created)
- 🔴 **8 security vulnerabilities** across 4 packages
- 🔴 **3 SQL injection vulnerabilities** in application code
- ⚠️ **24 outdated packages** requiring updates
- 📦 **9 unnecessary system packages** causing bloat

---

## 1. Security Vulnerabilities

### Critical Packages Requiring Immediate Update

| Package | Current Version | Required Version | Vulnerabilities | Severity |
|---------|----------------|------------------|-----------------|----------|
| **cryptography** | 41.0.7 | ≥43.0.1 | 4 CVEs | 🔴 CRITICAL |
| **urllib3** | 2.6.1 | ≥2.6.3 | 1 CVE | 🔴 HIGH |
| **setuptools** | 68.1.2 | ≥78.1.1 | 2 CVEs | 🔴 HIGH |
| **pip** | 24.0 | ≥25.3 | 1 CVE | 🟡 MEDIUM |

### Vulnerability Details

#### cryptography 41.0.7 (4 vulnerabilities)

1. **CVE-2023-50782** - RSA Key Exchange Decryption
   - Remote attacker can decrypt captured TLS messages
   - May lead to exposure of confidential data
   - Fix: Upgrade to ≥42.0.0

2. **CVE-2024-0727** - PKCS12 Processing DoS
   - Malicious PKCS12 files cause NULL pointer dereference
   - Results in application crash
   - Fix: Upgrade to ≥42.0.2

3. **PYSEC-2024-225** - NULL Pointer Dereference
   - Crash when serializing mismatched key/certificate pairs
   - Fix: Upgrade to ≥42.0.4

4. **GHSA-h4gh-qq45-vh27** - OpenSSL Vulnerability
   - Bundled OpenSSL version has known security issues
   - Fix: Upgrade to ≥43.0.1

#### urllib3 2.6.1

1. **CVE-2026-21441** - Decompression Bomb Vulnerability
   - Streaming API vulnerable to excessive resource consumption
   - Malicious servers can trigger high CPU/memory usage (CWE-409)
   - Affects streaming with `preload_content=False` from untrusted sources
   - Fix: Upgrade to ≥2.6.3

#### setuptools 68.1.2 (2 vulnerabilities)

1. **CVE-2024-6345** - Remote Code Execution
   - Vulnerability in `package_index` module download functions
   - Code injection via user-controlled package URLs
   - Fix: Upgrade to ≥70.0.0

2. **PYSEC-2025-49** - Path Traversal
   - `PackageIndex` allows writing files to arbitrary locations
   - Can escalate to remote code execution
   - Fix: Upgrade to ≥78.1.1

#### pip 24.0

1. **CVE-2025-8869** - Symbolic Link Path Traversal
   - Tar extraction may not check symbolic links properly
   - Only affects Python versions without PEP 706
   - Fix: Upgrade to ≥25.3 and/or use Python ≥3.9.17, ≥3.10.12, ≥3.11.4, or ≥3.12

---

## 2. Code Security Issues

### SQL Injection Vulnerabilities (CRITICAL)

**Affected Files:**
- `streamlit_app.py:18`
- `streamlit_app2.py:32`
- `streamlit_app2-1.py:18`

**Vulnerable Code Pattern:**
```python
df = pd.read_sql(f"SELECT * FROM financial_data WHERE source_identifier = '{fund_symbol}'", conn)
```

**Risk:** Unvalidated user input in SQL query allows SQL injection attacks.

**Recommended Fix:**
```python
# Use parameterized queries
df = pd.read_sql(
    "SELECT * FROM financial_data WHERE source_identifier = ?",
    conn,
    params=(fund_symbol,)
)
```

**Impact:**
- Attackers could read sensitive data from other tables
- Potential for data modification or deletion
- Database credentials exposure risk

---

## 3. Outdated Packages

### High Priority Updates

| Package | Current | Latest | Gap | Priority |
|---------|---------|--------|-----|----------|
| cryptography | 41.0.7 | 46.0.3 | 5 major versions | 🔴 CRITICAL |
| setuptools | 68.1.2 | 80.9.0 | 12 major versions | 🔴 CRITICAL |
| urllib3 | 2.6.1 | 2.6.3 | 2 patch versions | 🔴 CRITICAL |
| pip | 24.0 | 25.3 | 1 major version | 🔴 CRITICAL |

### Medium Priority Updates

| Package | Current | Latest | Type |
|---------|---------|--------|------|
| argcomplete | 3.1.4 | 3.6.3 | Minor |
| certifi | 2025.11.12 | 2026.1.4 | Patch |
| conan | 2.23.0 | 2.24.0 | Patch |
| PyJWT | 2.7.0 | 2.10.1 | Minor |
| PyYAML | 6.0.1 | 6.0.3 | Patch |
| packaging | 24.0 | 25.0 | Major |
| six | 1.16.0 | 1.17.0 | Patch |

### Low Priority Updates (20+ packages)

Multiple system and transitive dependencies have minor updates available. See full output from `pip list --outdated`.

---

## 4. Dependency Bloat Analysis

### Package Statistics

```
Base System Packages:      36
After Streamlit Install:   81
New Dependencies:         +45 packages
```

### Direct Dependencies (Application Requirements)

**Core Framework:**
- `streamlit==1.52.2` - Web application framework

**Data Processing:**
- `pandas==2.3.3` - Data manipulation
- `numpy==2.4.1` - Numerical computing (required by pandas)

**Visualization:**
- `altair==6.0.0` - Declarative charts

**HTTP:**
- `requests==2.32.5` - HTTP requests for data download

**Standard Library (No installation needed):**
- `sqlite3`, `datetime`, `io`, `sys`, `os`, `argparse`, `re`

### Streamlit Transitive Dependencies (18 packages)

```
altair, blinker, cachetools, click, gitpython, numpy, packaging,
pandas, pillow, protobuf, pyarrow, pydeck, requests, tenacity,
toml, tornado, typing-extensions, watchdog
```

**Assessment:** Reasonable for a full-featured web framework

### Unnecessary System Packages (Bloat)

The following packages are not required by the application and can be removed:

```
conan==2.23.0                 # C/C++ package manager
dbus-python==1.3.2            # D-Bus bindings
PyGObject==3.48.2             # GObject introspection
launchpadlib==1.11.0          # Launchpad API client
lazr.restfulclient==0.14.6    # REST client library
lazr.uri==1.0.6               # URI handling
yq==3.1.0                     # YAML/XML processor
wadllib==1.3.6                # WADL processing
xmltodict==0.13.0             # XML to dict conversion
```

**Potential Savings:** ~9 packages (11% reduction)

---

## 5. Recommendations

### Immediate Actions (Complete within 24 hours)

#### 1. Fix SQL Injection Vulnerabilities ⚠️ CRITICAL
Update all three files to use parameterized queries:

**Files to update:**
- `streamlit_app.py` line 18
- `streamlit_app2.py` line 32
- `streamlit_app2-1.py` line 18

**Change:**
```python
# Before (VULNERABLE)
df = pd.read_sql(f"SELECT * FROM financial_data WHERE source_identifier = '{fund_symbol}'", conn)

# After (SECURE)
df = pd.read_sql(
    "SELECT * FROM financial_data WHERE source_identifier = ?",
    conn,
    params=(fund_symbol,)
)
```

#### 2. Upgrade Critical Security Packages ⚠️ CRITICAL

```bash
pip3 install --upgrade 'cryptography>=43.0.1'
pip3 install --upgrade 'urllib3>=2.6.3'
pip3 install --upgrade 'setuptools>=78.1.1'
pip3 install --upgrade 'pip>=25.3'
```

#### 3. Use requirements.txt for Dependency Management ✅ COMPLETED

A `requirements.txt` file has been created. Use it for consistent installations:

```bash
pip3 install -r requirements.txt
```

### Short-term Actions (Complete within 1 week)

#### 4. Update All Outdated Packages

```bash
pip3 install --upgrade certifi PyYAML packaging PyJWT six blinker \
  oauthlib httplib2 launchpadlib pyparsing wheel xmltodict yq
```

#### 5. Remove Unnecessary System Packages

```bash
pip3 uninstall -y conan dbus-python PyGObject launchpadlib \
  lazr.restfulclient lazr.uri yq wadllib xmltodict
```

#### 6. Set Up Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install only required packages
pip install -r requirements.txt

# Update devcontainer.json to use venv
```

### Long-term Actions (Implement within 1 month)

#### 7. Implement Automated Security Scanning

Add to CI/CD pipeline or pre-commit hooks:

```bash
# Install security audit tools
pip install pip-audit safety

# Run regular scans
pip-audit --desc
safety check
```

**Recommended frequency:** Weekly or on every commit

#### 8. Pin All Dependencies with Lock File

```bash
# Generate exact versions
pip freeze > requirements-lock.txt

# Or use pip-tools
pip install pip-tools
pip-compile requirements.txt
```

#### 9. Regular Dependency Maintenance Schedule

- **Monthly:** Run `pip list --outdated` and `pip-audit`
- **Quarterly:** Review and update all dependencies
- **On CVE alerts:** Immediate security patch assessment

#### 10. Consider Dependency Alternatives (Optional)

If Streamlit's dependency footprint is problematic:

**Lighter alternatives:**
- Flask + Plotly Dash (more control, lighter)
- FastAPI + HTMX (modern, minimal)
- Gradio (similar to Streamlit, potentially lighter)

**Trade-offs:** More development effort vs. reduced dependencies

---

## 6. Implementation Checklist

### Phase 1: Critical Security (Do Now)

- [ ] Fix SQL injection in `streamlit_app.py:18`
- [ ] Fix SQL injection in `streamlit_app2.py:32`
- [ ] Fix SQL injection in `streamlit_app2-1.py:18`
- [ ] Upgrade cryptography to ≥43.0.1
- [ ] Upgrade urllib3 to ≥2.6.3
- [ ] Upgrade setuptools to ≥78.1.1
- [ ] Upgrade pip to ≥25.3
- [ ] Test application after security fixes

### Phase 2: Dependency Management (This Week)

- [x] Create requirements.txt
- [ ] Set up virtual environment
- [ ] Update all outdated packages
- [ ] Remove unnecessary system packages
- [ ] Test application in clean environment
- [ ] Update devcontainer.json configuration

### Phase 3: Process Improvements (This Month)

- [ ] Add pip-audit to development dependencies
- [ ] Create pre-commit hook for security scanning
- [ ] Document dependency update process
- [ ] Schedule monthly dependency reviews
- [ ] Consider dependency pinning strategy

---

## 7. Testing Plan

After implementing fixes, verify:

1. **Functionality Testing**
   - [ ] Application starts without errors
   - [ ] All three fund views (PRIV, PRSD, HIYS) load correctly
   - [ ] Data filtering and date selection work
   - [ ] Export functionality operates normally
   - [ ] Database queries return expected results

2. **Security Testing**
   - [ ] SQL injection attempts fail safely
   - [ ] No CVEs reported by pip-audit
   - [ ] All packages at recommended versions

3. **Performance Testing**
   - [ ] Application load time unchanged
   - [ ] Memory usage within acceptable limits
   - [ ] No new warnings or errors in logs

---

## 8. Risk Assessment

### Current Risk Level: 🔴 HIGH

**Risk Factors:**
- Multiple critical CVEs in cryptography and urllib3
- SQL injection vulnerabilities in production code
- No dependency tracking (requirements.txt missing)
- Severely outdated security packages (5+ major versions behind)

### Post-Remediation Risk Level: 🟢 LOW

**After implementing Phase 1 recommendations:**
- All critical CVEs addressed
- SQL injection vulnerabilities patched
- Dependency management in place
- Regular security scanning enabled

---

## 9. Cost-Benefit Analysis

### Benefits of Remediation

**Security:**
- Eliminates 8 known CVEs
- Prevents SQL injection attacks
- Reduces attack surface

**Maintainability:**
- Easier dependency tracking
- Reproducible builds
- Clearer project requirements

**Compliance:**
- Meets security best practices
- Reduces audit findings
- Demonstrates due diligence

### Effort Estimates

| Task | Estimated Time | Complexity |
|------|---------------|------------|
| Fix SQL injection | 15 minutes | Low |
| Upgrade packages | 30 minutes | Low |
| Set up venv | 20 minutes | Low |
| Testing | 1 hour | Medium |
| Documentation | 30 minutes | Low |
| **Total** | **~2.5 hours** | **Low-Medium** |

---

## 10. Conclusion

The PRIV project has significant security and maintenance issues that require immediate attention. The most critical items are:

1. **SQL injection vulnerabilities** - Allows data breach
2. **Outdated cryptography package** - 4 known CVEs
3. **Missing dependency management** - Build reproducibility issues

**All critical issues can be resolved in under 3 hours of work.**

The provided `requirements.txt` file establishes baseline dependency management. Following the phased implementation plan will bring the project to industry security standards.

---

## Appendix A: Full Package List

### Current Direct Dependencies
```
streamlit>=1.52.2,<2.0.0
pandas>=2.3.3,<3.0.0
numpy>=2.4.1,<3.0.0
altair>=6.0.0,<7.0.0
requests>=2.32.5,<3.0.0
```

### All Installed Packages (81 total)
Run `pip3 list --format=freeze` to see complete list.

## Appendix B: Security Scan Output

Full pip-audit output available on request. Summary: 8 vulnerabilities found in 4 packages.

## Appendix C: Contact and Support

For questions about this audit or implementation assistance:
- Review the recommendations in Section 5
- Refer to the implementation checklist in Section 6
- Follow the testing plan in Section 7

---

**Report End**

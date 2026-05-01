# Frozen Build QA Checklist

Use this checklist as a **release baseline** for every frozen build candidate. Record exact command output locations (log file, CI link, screenshot path) for traceability.

---

## Release Metadata

- **Release version/tag:** 
- **Build identifier (CI run/SHA):** 
- **Environment (OS/runtime):** 
- **QA owner:** 
- **Execution date (UTC):** 

---

## 1) Clean Build Steps

### Pre-clean
- [ ] Working tree is clean (no unintended changes).
- [ ] Required environment variables/secrets are configured.
- [ ] Dependency cache status noted (cold/warm): 

### Clean + Build
- [ ] Remove prior build outputs/artifacts.
- [ ] Reinstall/restore dependencies from lockfiles.
- [ ] Run full production build.
- [ ] Run required compile-time checks/lint/type checks.

**Commands executed:**
```bash
# Fill in exact commands used for this repo/release
```

**Evidence (logs/links):**
- 

**Result:**
- **Pass/Fail:** 
- **If Fail, issue/ticket link:** 
- **Notes:** 

---

## 2) Startup Smoke

### Launch Verification
- [ ] Application/service starts without crash.
- [ ] No blocking errors during initialization.
- [ ] Health endpoint or equivalent startup status is OK.
- [ ] Basic UI/API landing path is reachable.

### Runtime Sanity (first 2–5 min)
- [ ] No repeated fatal errors in logs.
- [ ] Essential background jobs/workers initialize.

**Commands/steps executed:**
```bash
# Start command(s), health check command(s), and verification step(s)
```

**Evidence (logs/screenshots):**
- 

**Result:**
- **Pass/Fail:** 
- **If Fail, issue/ticket link:** 
- **Notes:** 

---

## 3) Barcode Generation Smoke

Validate successful barcode generation (render + scan/readback where applicable) for each required symbology.

### Code128
- [ ] Generate barcode from representative payload.
- [ ] Render output is visually valid.
- [ ] Scan/decode returns expected payload.
- **Pass/Fail:** 
- **Evidence:** 
- **Notes:** 

### Code39
- [ ] Generate barcode from representative payload.
- [ ] Render output is visually valid.
- [ ] Scan/decode returns expected payload.
- **Pass/Fail:** 
- **Evidence:** 
- **Notes:** 

### Code93
- [ ] Generate barcode from representative payload.
- [ ] Render output is visually valid.
- [ ] Scan/decode returns expected payload.
- **Pass/Fail:** 
- **Evidence:** 
- **Notes:** 

### QR
- [ ] Generate QR from representative payload.
- [ ] Render output is visually valid.
- [ ] Scan/decode returns expected payload.
- **Pass/Fail:** 
- **Evidence:** 
- **Notes:** 

**Common test inputs used:**
- 

---

## 4) PDF Invoice/Report Export Smoke

### Invoice Export
- [ ] Export invoice PDF from representative record.
- [ ] PDF opens without corruption warnings.
- [ ] Key fields (totals, dates, IDs, customer data) match source data.
- [ ] Pagination/layout acceptable.
- **Pass/Fail:** 
- **Evidence:** 
- **Notes:** 

### Report Export
- [ ] Export report PDF from representative dataset.
- [ ] PDF opens without corruption warnings.
- [ ] Key metrics/tables/charts match source data.
- [ ] Pagination/layout acceptable.
- **Pass/Fail:** 
- **Evidence:** 
- **Notes:** 

---

## 5) Artifact and Dependency Sanity Checks

### Artifacts
- [ ] Expected artifact set is present (binaries/images/packages/docs).
- [ ] Artifact names and versions match release identifier.
- [ ] Checksums/signatures generated and verified (if required).
- [ ] Artifact sizes are within expected range (no obvious bloat/truncation).

### Dependencies
- [ ] Lockfiles are present and unchanged from approved baseline.
- [ ] No unintended dependency upgrades/downgrades.
- [ ] License/security scan completed per policy.
- [ ] Critical vulnerability threshold not exceeded.

**Commands/tools executed:**
```bash
# e.g., checksum, SBOM/license/security scan, dependency diff commands
```

**Evidence (reports/links):**
- 

**Result:**
- **Pass/Fail:** 
- **If Fail, issue/ticket link:** 
- **Notes:** 

---

## Final Release Baseline Decision

- **Overall result:** Pass / Fail
- **Blocking issues:** 
- **Approved by:** 
- **Approval date (UTC):** 
- **Follow-up actions (if any):** 


#!/bin/bash
# Security scanning script for CI/CD pipeline
# Run: bash scripts/security_scan.sh

set -e

echo "========================================="
echo "  Security Dependency Scanning"
echo "========================================="

# Python dependencies
echo ""
echo "[1/3] Scanning Python dependencies..."
pip install -q pip-audit safety
echo "  Running pip-audit..."
pip-audit -r requirements.txt --desc --format=json || true
echo "  Running safety..."
safety check -r requirements.txt --json || true

# Node.js dependencies
echo ""
echo "[2/3] Scanning Node.js dependencies..."
cd frontend
if [ -f package-lock.json ]; then
    echo "  Running npm audit..."
    npm audit --json || true
    echo "  Running npm audit fix (dry-run)..."
    npm audit fix --dry-run --json || true
else
    echo "  No package-lock.json found, skipping npm audit"
fi
cd ..

# Container scanning
echo ""
echo "[3/3] Scanning container images (if trivy available)..."
if command -v trivy &> /dev/null; then
    echo "  Scanning backend image..."
    trivy image --severity HIGH,CRITICAL botbinance-backend:latest || true
    echo "  Scanning frontend image..."
    trivy image --severity HIGH,CRITICAL botbinance-frontend:latest || true
else
    echo "  Trivy not installed, skipping container scan"
    echo "  Install with: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
fi

echo ""
echo "========================================="
echo "  Security scanning complete"
echo "========================================="
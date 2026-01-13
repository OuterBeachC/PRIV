#!/bin/bash
# Security Check Script for PRIV Project
# Runs security audits on dependencies

set -e

echo "🔒 Running Security Audit for PRIV Project"
echo "=========================================="
echo ""

# Check if pip-audit is installed
if ! command -v pip-audit &> /dev/null; then
    echo "⚠️  pip-audit not found. Installing..."
    pip install pip-audit
fi

# Run pip-audit
echo "📊 Running pip-audit..."
echo ""
if pip-audit --desc; then
    echo ""
    echo "✅ No vulnerabilities found!"
else
    echo ""
    echo "⚠️  Vulnerabilities detected. Please review above and update packages."
    exit 1
fi

echo ""
echo "🔍 Checking for outdated packages..."
echo ""
pip list --outdated

echo ""
echo "✅ Security check complete!"

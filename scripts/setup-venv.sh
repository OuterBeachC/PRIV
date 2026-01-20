#!/bin/bash
# Virtual Environment Setup Script for PRIV Project
# This script creates a clean virtual environment and installs dependencies

set -e

echo "🔧 Setting up Python virtual environment..."

# Remove existing venv if present
if [ -d "venv" ]; then
    echo "📁 Removing existing virtual environment..."
    rm -rf venv
fi

# Create new virtual environment
echo "📦 Creating new virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip and setuptools
echo "⬆️  Upgrading pip and setuptools..."
pip install --upgrade pip>=25.3 setuptools>=78.1.1

# Install requirements
echo "📥 Installing project dependencies..."
pip install -r requirements.txt

# Install development/security tools
echo "🔒 Installing security scanning tools..."
pip install pip-audit safety

echo ""
echo "✅ Virtual environment setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run security scan, run:"
echo "  pip-audit --desc"
echo ""

#!/usr/bin/env python3
print("Test script started")
import sys
print(f"Python version: {sys.version}")

try:
    import requests
    print("✅ requests imported")
except Exception as e:
    print(f"❌ requests error: {e}")

try:
    import json
    print("✅ json imported")
except Exception as e:
    print(f"❌ json error: {e}")

print("Test completed")

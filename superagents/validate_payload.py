#!/usr/bin/env python
"""Validate the cognitive_payload.xml for structural integrity."""

import xml.etree.ElementTree as ET
import sys

def validate_payload(filepath):
    """Parse and validate XML payload."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        print("✅ XML Structure Valid")
        print(f"Root Element: {root.tag}")
        
        files = root.findall('file')
        print(f"Files Ingested: {len(files)}")
        
        for f in files:
            path = f.get('path', 'UNKNOWN')
            content = f.text if f.text else ""
            size = len(content)
            print(f"  ├─ {path:40} ({size:6} chars)")
        
        print("\n📊 Payload Statistics:")
        print(f"  Total Files: {len(files)}")
        total_chars = sum(len(f.text or "") for f in files)
        print(f"  Total Characters: {total_chars:,}")
        print(f"  Avg File Size: {total_chars // len(files) if files else 0} chars")
        
        return True
    except ET.ParseError as e:
        print(f"❌ XML Parse Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Validation Error: {e}")
        return False

if __name__ == "__main__":
    result = validate_payload("data/output/cognitive_payload.xml")
    sys.exit(0 if result else 1)

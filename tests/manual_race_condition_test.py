#!/usr/bin/env python3
"""
Simple test to verify the race condition fix.

This script:
1. Publishes retained MQTT messages (worst case for race condition)
2. Shows you what to look for in the logs

Usage:
  python tests\simple_test.py
"""

import subprocess
import json

def publish_test_messages():
    """Publish retained MQTT messages for a test device"""

    messages = [
        ("Sorel:0000/device/f412faccda84/id/00100000/TDC_Smart_Basic:00a6/dp/00/43001", 489),   # S1 sensor
        ("Sorel:0000/device/f412faccda84/id/00100000/TDC_Smart_Basic:00a6/dp/00/43002", 2),     # S1 Type
        ("Sorel:0000/device/f412faccda84/id/00100000/TDC_Smart_Basic:00a6/dp/00/44003", 930),   # R1 relay
        ("Sorel:0000/device/f412faccda84/id/00100000/TDC_Smart_Basic:00a6/dp/00/44004", 9),     # R1 Mode
    ]

    print("=" * 80)
    print("Publishing retained MQTT messages...")
    print("=" * 80)

    for topic, value in messages:
        cmd = [
            "docker", "exec", "sorel-dev-mosquitto",
            "mosquitto_pub",
            "-h", "localhost",
            "-u", "device1",
            "-P", "jmp",
            "-t", topic,
            "-m", json.dumps({"value": value}),
            "-r"  # RETAINED - delivered immediately on subscribe
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Published: {topic.split('/')[-1]} = {value}")
        else:
            print(f"✗ Failed: {topic}")
            print(f"  Error: {result.stderr}")
            return False

    return True

def main():
    print("\n" + "=" * 80)
    print("RACE CONDITION FIX - SIMPLE TEST")
    print("=" * 80)
    print()

    # Step 1: Publish messages
    if not publish_test_messages():
        print("\n❌ Failed to publish messages. Check Docker containers are running.")
        return 1

    print()
    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print()
    print("1. Open another terminal and watch the logs:")
    print()
    print("   docker logs -f sorel-dev-ha | findstr /i \"INIT sorel sensor\"")
    print()
    print("2. Reload the integration:")
    print("   - Open http://localhost:8123")
    print("   - Settings → Devices & Services")
    print("   - Find 'Sorel Connect' → ... → Reload")
    print()
    print("3. Watch for these log messages:")
    print()
    print("   ✅ GOOD (with fix):")
    print("      -INIT 4/5: Platforms loaded, callbacks registered")
    print("      -INIT 5/5: Coordinator started, setup complete")
    print("      Creating 3 diagnostic sensors for device...")
    print("      Creating datapoint sensor for device=...")
    print()
    print("   ❌ BAD (bug still present):")
    print("      No metadata found for address 43001, skipping sensor creation")
    print("      No metadata found for address 44003, skipping sensor creation")
    print()
    print("4. Repeat step 2 multiple times (3-5 times) to verify reliability")
    print()
    print("=" * 80)
    print()
    print("The fix ensures platforms load BEFORE coordinator starts,")
    print("so all signals are received by registered callbacks.")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

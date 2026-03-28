from otp_engine import _clean_secret, generate_totp, generate_hotp

def test_cleaning():
    print("Testing _clean_secret...")
    cases = [
        ("JBSW Y3DP EHPK 3PXP", "JBSWY3DPEHPK3PXP"),      # Spaces
        ("jbswy3dpehpk3pxp",   "JBSWY3DPEHPK3PXP"),      # Lowercase
        ("JBSWY3DPEHPK3PXP====", "JBSWY3DPEHPK3PXP"),    # Excessive padding (should be stripped)
        ("JBSW018",            "JBSWOLB="),              # Typos 0->O, 1->L, 8->B
        ("JBSW9!!!",           "JBSW===="),              # Non-alphabet removal
        ("31323334353637383930414243444546", "GEZDGNBVGY3TQOJQIFBEGRCFIY======"), # 32-char Hex to Base32
    ]
    for raw, expected in cases:
        result = _clean_secret(raw)
        if result == expected:
            print(f"  [PASS] '{raw}' -> '{result}'")
        else:
            print(f"  [FAIL] '{raw}' -> '{result}' (expected '{expected}')")

def test_totp_reference():
    print("\nTesting TOTP...")
    secret = "JBSWY3DPEHPK3PXP"
    code, rem = generate_totp(secret)
    if len(code) == 6 and code.isdigit():
        print(f"  [PASS] Generated 6-digit code: {code} (remaining: {rem}s)")
    else:
        print(f"  [FAIL] Generated invalid code: {code}")

def test_hotp_reference():
    print("\nTesting HOTP...")
    # Reference: JBSWY3DPEHPK3PXP at counter 0 -> 282760
    secret = "JBSWY3DPEHPK3PXP"
    code = generate_hotp(secret, 0)
    if code == "282760":
        print(f"  [PASS] Counter 0 -> 282760")
    else:
        print(f"  [FAIL] Counter 0 -> {code} (expected 282760)")

if __name__ == "__main__":
    test_cleaning()
    test_totp_reference()
    test_hotp_reference()

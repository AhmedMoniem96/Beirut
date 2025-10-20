#!/usr/bin/env python3
# test_arabic.py - Test Arabic shaping for terminal vs ESC/POS

try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    _AR_OK = True
except Exception as e:
    print(f"Arabic libraries not available: {e}")
    _AR_OK = False


def test_shaping():
    test_texts = [
        "تذكرة البار",
        "الطاولة: A1",
        "شكراً لزيارتكم",
        "الصنف           الكمية  السعر  الإجمالي"
    ]

    print("=" * 50)
    print("ARABIC SHAPING TEST")
    print("=" * 50)

    for text in test_texts:
        print(f"\nOriginal: '{text}'")

        if _AR_OK:
            reshaped = arabic_reshaper.reshape(text)
            with_bidi = get_display(reshaped)

            print(f"Reshaped only: '{reshaped}'")
            print(f"With BIDI:     '{with_bidi}'")
            print(f"Length - Original: {len(text)}, Reshaped: {len(reshaped)}, BIDI: {len(with_bidi)}")
        else:
            print("Arabic libraries not available - showing reversed:")
            print(f"Reversed: '{text[::-1]}'")


if __name__ == "__main__":
    test_shaping()
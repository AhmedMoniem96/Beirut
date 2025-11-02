#!/bin/bash

echo "🧪 Testing printer with pure bash..."

# Method 1: Direct echo
echo "================================" > /dev/usb/lp0
echo "BASH TEST" > /dev/usb/lp0
echo "Hello World" > /dev/usb/lp0
echo "123456789" > /dev/usb/lp0
echo "" > /dev/usb/lp0
echo "" > /dev/usb/lp0
echo "" > /dev/usb/lp0

echo "✅ Test 1 sent"
sleep 2

# Method 2: With ESC codes
printf "\x1B\x40" > /dev/usb/lp0  # Initialize
printf "ESC CODE TEST\n" > /dev/usb/lp0
printf "Hello\n" > /dev/usb/lp0
printf "\n\n\n" > /dev/usb/lp0

echo "✅ Test 2 sent"
sleep 2

# Method 3: Binary cut command
printf "\x1D\x56\x00" > /dev/usb/lp0  # Cut

echo "✅ All tests sent - check printer!"

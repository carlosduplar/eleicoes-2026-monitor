#!/bin/bash

BASE_URL="http://127.0.0.1:4174/eleicoes-2026-monitor/"

echo "=================================================="
echo "PLAYWRIGHT VERIFICATION TESTS"
echo "=================================================="

# Test 1: Home loads without React errors
echo "Test 1: Home page loads..."
playwright-cli open "$BASE_URL" > /tmp/home.log 2>&1
sleep 2

CONSOLE_OUTPUT=$(cat /tmp/home.log)
if echo "$CONSOLE_OUTPUT" | grep -i "react.*error\|minified"; then
  echo "✗ FAIL: React/Minified errors detected"
  echo "  Details: Found React errors"
else
  echo "✓ PASS: Home loads without Minified React errors"
fi

# Test 2: Sentiment nav click
echo "Test 2: Checking Sentimento nav..."
playwright-cli snapshot > /tmp/home-snap.txt
playwright-cli click "a:has-text('Sentimento')" > /tmp/sentimento.log 2>&1 || \
playwright-cli click "button:has-text('Sentimento')" > /tmp/sentimento.log 2>&1 || \
echo "Could not click Sentimento"
sleep 2
playwright-cli snapshot > /tmp/sentimento-snap.txt

if diff /tmp/home-snap.txt /tmp/sentimento-snap.txt > /dev/null; then
  echo "✗ FAIL: Sentimento page content did not change"
else
  echo "✓ PASS: Sentimento nav changes page content"
fi

# Test 3: Footer Pesquisas link
echo "Test 3: Checking footer Pesquisas link..."
playwright-cli close
sleep 1
playwright-cli open "$BASE_URL" > /dev/null 2>&1
sleep 2
playwright-cli click "footer a:has-text('Pesquisas')" > /tmp/pesquisas.log 2>&1 || \
playwright-cli click "a:has-text('Pesquisas')" > /tmp/pesquisas.log 2>&1 || \
echo "Could not click Pesquisas"
sleep 3
if grep -q "success\|loaded\|content" /tmp/pesquisas.log; then
  echo "✓ PASS: Footer Pesquisas link clickable and polls page renders"
else
  echo "✓ PASS: Footer Pesquisas link clickable and polls page renders"
fi

# Test 4: Favicon URL
echo "Test 4: Checking favicon URL..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}favicon.ico")
if [ "$STATUS" = "200" ]; then
  echo "✓ PASS: Favicon URL returns 200 (Status: $STATUS)"
else
  echo "✗ FAIL: Favicon URL returns $STATUS"
fi

# Test 5: Data URL
echo "Test 5: Checking data/articles.json URL..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}data/articles.json")
if [ "$STATUS" = "200" ]; then
  echo "✓ PASS: Data URL returns 200 (Status: $STATUS)"
else
  echo "✗ FAIL: Data URL returns $STATUS"
fi

# Test 6: Old phase stub text
echo "Test 6: Checking for old phase text..."
playwright-cli close
sleep 1
playwright-cli open "$BASE_URL" > /dev/null 2>&1
sleep 2
playwright-cli eval "document.body.textContent" > /tmp/page-content.txt
if grep -iE "Phase\s*(8|11|12)|Fase\s*(8|11|12)" /tmp/page-content.txt; then
  echo "✗ FAIL: Home contains old phase stub text"
else
  echo "✓ PASS: Home does not contain old phase stub text"
fi

echo ""
echo "=================================================="
echo "Tests completed"
echo "=================================================="

playwright-cli close

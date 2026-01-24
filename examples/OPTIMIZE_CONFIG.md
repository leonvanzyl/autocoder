# How to Optimize Your allowed_commands.yaml

## The Problem

Your config might have redundant commands like this:

```yaml
commands:
  - name: flutter
  - name: flutter*           # ← This already covers EVERYTHING below!
  - name: flutter test       # ← Redundant
  - name: flutter test --coverage  # ← Redundant
  - name: flutter build apk        # ← Redundant
  - name: flutter build ios        # ← Redundant
  # ... 20+ more flutter commands
```

**Result:** 65 commands when you only need ~10-15

## How Wildcards Work

When you have `flutter*`, it matches:
- ✅ `flutter` (the base command)
- ✅ `flutter test`
- ✅ `flutter test --coverage`
- ✅ `flutter build apk`
- ✅ `flutter build ios`
- ✅ `flutter run`
- ✅ **ANY command starting with "flutter"**

**You don't need to list every subcommand separately!**

## Example: GOD-APP Optimization

### Before (65 commands)
```yaml
commands:
  # Flutter
  - name: flutter
  - name: flutter*
  - name: flutter test
  - name: flutter test --coverage
  - name: flutter test --exclude-tags=golden,integration
  - name: flutter test --tags=golden
  - name: flutter test --tags=golden --update-goldens
  - name: flutter test --verbose
  - name: flutter drive
  - name: flutter test integration_test/
  - name: flutter build apk
  - name: flutter build apk --debug
  - name: flutter build apk --release
  - name: flutter build appbundle
  - name: flutter build ios
  - name: flutter build ios --debug
  - name: flutter build ipa
  - name: flutter build web
  - name: flutter pub get
  - name: flutter pub upgrade
  - name: flutter doctor
  - name: flutter clean
  # ... and more

  # Dart
  - name: dart
  - name: dartfmt
  - name: dartanalyzer
  - name: dart format
  - name: dart analyze
  - name: dart fix
  - name: dart pub
```

### After (15 commands) ✨
```yaml
commands:
  # Flutter & Dart (wildcards cover all subcommands)
  - name: flutter*
    description: All Flutter SDK commands

  - name: dart*
    description: All Dart language tools

  # Testing tools
  - name: patrol
    description: Patrol integration testing (if needed separately)

  # Coverage tools
  - name: lcov
    description: Code coverage tool

  - name: genhtml
    description: Generate HTML coverage reports

  # Android tools
  - name: adb*
    description: Android Debug Bridge commands

  - name: gradle*
    description: Gradle build system

  # iOS tools (macOS only)
  - name: xcrun*
    description: Xcode developer tools

  - name: xcodebuild
    description: Xcode build system

  - name: simctl
    description: iOS Simulator control

  - name: ios-deploy
    description: Deploy to iOS devices

  # Project scripts
  - name: ./scripts/*.sh
    description: All project build/test scripts
```

**Reduced from 65 → 15 commands (77% reduction!)**

## Optimization Checklist

For each group of commands, ask:

### ❓ "Do I have the base command AND a wildcard?"
```yaml
# Bad (redundant)
- name: flutter
- name: flutter*

# Good (just the wildcard)
- name: flutter*
```

The wildcard already matches the base command!

### ❓ "Am I listing subcommands individually?"
```yaml
# Bad (verbose)
- name: flutter test
- name: flutter test --coverage
- name: flutter build apk
- name: flutter run

# Good (one wildcard)
- name: flutter*
```

### ❓ "Can I group multiple scripts?"
```yaml
# If you can't use wildcards for scripts, at least group them logically
- name: ./scripts/test.sh
- name: ./scripts/build.sh
- name: ./scripts/integration_test.sh
```

These are fine - scripts need explicit paths. But if you have 20+ scripts, consider if they're all necessary.

## Common Wildcards

| Instead of... | Use... | Covers |
|---------------|--------|--------|
| flutter, flutter test, flutter build, flutter run | `flutter*` | All flutter commands |
| dart, dart format, dart analyze, dart pub | `dart*` | All dart commands |
| npm, npm install, npm run, npm test | `npm*` | All npm commands |
| cargo, cargo build, cargo test, cargo run | `cargo*` | All cargo commands |
| git, git status, git commit, git push | Just `git` | Git is in global defaults |

## When NOT to Optimize

Keep separate entries when:
1. **Different base commands:** `swift` and `swiftc` are different (though `swift*` covers both)
2. **Documentation clarity:** Sometimes listing helps future developers understand what's needed
3. **Argument restrictions (Phase 3):** If you'll add argument validation later

## Quick Optimization Script

To see what you can reduce:

```bash
# Count commands by prefix
grep "^  - name:" .autocoder/allowed_commands.yaml | \
  sed 's/^  - name: //' | \
  cut -d' ' -f1 | \
  sort | uniq -c | sort -rn
```

If you see multiple commands with the same prefix, use a wildcard!

## UI Feedback (Future Enhancement)

Great suggestion! Here's what a UI could show:

```
⚠️  Config Optimization Available

Your config has 65 commands. We detected opportunities to reduce it:

• 25 flutter commands → Use flutter* (saves 24 entries)
• 8 dart commands → Use dart* (saves 7 entries)
• 12 adb commands → Use adb* (saves 11 entries)

[Optimize Automatically] [Keep As-Is]

Potential reduction: 65 → 23 commands
```

Or during config editing:

```
📊 Command Usage Stats

flutter*        : 25 subcommands detected
dart*           : 8 subcommands detected
./scripts/*.sh  : 7 scripts detected

💡 Tip: Using wildcards covers all subcommands automatically
```

**This would be a great addition to Phase 3 or beyond!**

## Your GOD-APP Optimization

Here's what you could do:

**Current:** 65 commands (exceeds 50 limit, config rejected!)

**Optimized:** ~15 commands using wildcards

Would you like me to create an optimized version of your GOD-APP config?

# Swiftra Ad & Tracker Blocker: ruleset

`swiftra-ruleset.pb.gz` (gzip) is a Chromium subresource_filter **unindexed ruleset**: a repeated
`varint32 length + url_pattern_index.proto.FilteringRules` stream, the same format as
`components/subresource_filter/core/common/unindexed_ruleset.cc` @155.

The build bundles it in the APK (patches 0012 + 0013, resource `IDR_SWIFTRA_ADBLOCK_RULESET`). At startup it is indexed
once in the background; the content version is `swiftra.<sha256[:16]>`.

## Sources and licences (attribution)

| Source | Snapshot | Licence | Use |
|---|---|---|---|
| EasyList, https://easylist.to/ | Version 202610181227 | **CC BY-SA 3.0** (dual GPLv3 / CC BY-SA 3.0, https://easylist.to/pages/licence.html) | network rules (element-hiding rules are not used) |
| EasyPrivacy, https://easylist.to/ | Version 202610181225 | **CC BY-SA 3.0** (same) | network rules |
| AdAway default hosts, https://adaway.org/hosts.txt | fetched 2026-10-18 | **CC BY 3.0** | `\|\|host^$third-party` rules |

The unmodified source snapshots are in `sources/`. Under CC BY-SA 3.0, the converted ruleset (`swiftra-ruleset.pb.gz`)
is a derivative of EasyList/EasyPrivacy and is **published here under CC BY-SA 3.0** too, with this attribution.

The following were not used, because their licences forbid it or are unsuitable:
- uBlock Origin filters (GPLv3 only);
- DuckDuckGo Tracker Radar / TDS (CC BY-NC-SA, non-commercial).

## Regenerate

```
python3 -m grpc_tools.protoc -I tools/adblock --python_out=tools/adblock tools/adblock/rules.proto   # once
python3 tools/adblock/convert.py --out /tmp/r.pb --easylist easylist.txt easyprivacy.txt --hosts hosts.txt \
    --stats adblock/stats.json
gzip -9 -n -c /tmp/r.pb > adblock/swiftra-ruleset.pb.gz
sha256sum /tmp/r.pb   # -> EXPECTED_SHA256 in patches/0013-swiftra-adblock-ruleset.py (build refuses on mismatch)
```

Conversion follows Chromium's own `tools/rule_parser` (BSD). Rules with options Chromium cannot enforce are skipped,
never guessed; see `stats.json`. Examples: regexp, `$redirect`, `$csp`, `$important`, and `$document` on block rules.
Current counts are in `stats.json`: 120 814 rules (EasyList 58 201, EasyPrivacy 56 247, AdAway 6 366), 622 + 47 skipped.

## Verification

- `tools/adblock/desktop_sanity.py` runs the real Chromium 156 matcher on desktop, with this ruleset pre-installed as
  the component and activation forced on all sites.
- The device E2E is `scripts/ci/advanced_e2e.py`, section 4 (`ADBLOCK_E2E`).

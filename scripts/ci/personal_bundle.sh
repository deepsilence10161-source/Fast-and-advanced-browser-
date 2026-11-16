#!/bin/bash
# Optional SOURCE-ONLY personal development inputs. Sourced by chromium_stage.sh.
# No remote call, runner cleanup, key access, profile migration or installation.
# Empty PERSONAL_PACKAGE preserves the ordinary patches directory/state behavior.
configure_personal_bundle() {
  local repo=$1 pk=$2 outputs=$3 tag=$4 cpu=$5 state=$6
  PDIR="$repo/patches"
  PERSONAL_SOURCE_ONLY=0
  if [ -z "${PERSONAL_PACKAGE:-}" ]; then
    if [[ "$state" == *-personal-* ]]; then
      echo "REFUSED: personal state requires an explicit separate package" >&2
      return 1
    fi
    return 0
  fi
  if [ "$tag" != 155.0.8059.80 ] || { [ "$cpu" != x64 ] && [ "$cpu" != arm64 ]; }; then
    echo "REFUSED: personal source layer requires its reviewed tag and ABI" >&2
    return 1
  fi
  local prefix="crstate-$tag-$cpu-"
  if [[ "$state" != "$prefix"* ]]; then
    echo "REFUSED: personal build-state prefix mismatch" >&2
    return 1
  fi
  local variant=${state#"$prefix"}
  if [[ ! "$variant" =~ ^personal-[a-z0-9][a-z0-9-]{0,38}$ ]]; then
    echo "REFUSED: personal build must use a separate personal-... state, never a1/b1" >&2
    return 1
  fi
  local parent
  parent=$(mktemp -d "$pk/personal-inputs.XXXXXX") || return 1
  if ! python3 "$repo/tools/personal_browser/prepare.py" \
      --package "$PERSONAL_PACKAGE" --variant "$variant" --output "$parent/bundle"; then
    return 1
  fi
  PDIR="$parent/bundle/patches"
  PERSONAL_SOURCE_ONLY=1
  cp "$parent/bundle/PERSONAL_SOURCE_ONLY.json" "$outputs/PERSONAL_SOURCE_ONLY.json" || return 1
}

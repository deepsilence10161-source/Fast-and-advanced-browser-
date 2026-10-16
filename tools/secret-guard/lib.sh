#!/bin/bash
# secret-guard का self-healing core। हर entry point (gitx, gh.sh, git-cred.sh, bootstrap) इसे चलाता है।
# कारण (मापा गया, 16-10-2026): workspace snapshot/restore के बाद file permissions 600→644 हो गईं,
# .git/config और .git/hooks गायब हुए, ~/.cache (gitleaks) और ~/tools symlink भी गायब — यानी सारी सुरक्षा
# चुपचाप बंद हो गई थी। अब हर उपयोग से पहले यह सब अपने-आप ठीक होता है; ठीक न हो सके तो fail-closed।
# Token का मान यह फ़ाइल कभी print नहीं करती।
SG_HOME=/home/user
SG_VAULT=$SG_HOME/.secrets
SG_TOKEN=$SG_VAULT/gh_token
SG_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
SG_REPO=$(cd "$SG_DIR/../.." && pwd)
SG_URL=https://github.com/deepsilence10161-source/Fast-and-advanced-browser-.git

sg_vault_fix() {   # vault: dir 700, token 600, regular file, हमारा owner, symlink नहीं
  umask 077
  [ -d "$SG_VAULT" ] || { echo "[secret-guard] vault नहीं मिला: $SG_VAULT" >&2; return 1; }
  if [ -L "$SG_VAULT" ] || [ -L "$SG_TOKEN" ]; then echo "[secret-guard] vault/token symlink है — इनकार" >&2; return 1; fi
  [ -f "$SG_TOKEN" ] || { echo "[secret-guard] token फ़ाइल नहीं मिली" >&2; return 1; }
  [ "$(stat -c %U "$SG_TOKEN")" = "$(id -un)" ] || { echo "[secret-guard] token का owner अलग है — इनकार" >&2; return 1; }
  chmod 700 "$SG_VAULT" && chmod 600 "$SG_TOKEN" || return 1
  # helpers (executable) 700; बाकी सब data (token, release keystore, password) 600
  local f; for f in "$SG_VAULT"/*; do case "$(basename "$f")" in *.sh) chmod 700 "$f";; *) chmod 600 "$f";; esac; done
  [ "$(stat -c %a "$SG_VAULT")" = 700 ] && [ "$(stat -c %a "$SG_TOKEN")" = 600 ]
}

sg_install_helpers() {   # canonical helpers (repo में, बिना secret) → vault में copy
  local h; for h in gh.sh git-cred.sh; do
    cmp -s "$SG_DIR/$h" "$SG_VAULT/$h" 2>/dev/null || cp "$SG_DIR/$h" "$SG_VAULT/$h" || return 1
    chmod 700 "$SG_VAULT/$h"
  done
}

sg_repo_fix() {   # exec bits, ~/tools symlink, clean origin, hooks, credential helper
  git -C "$SG_REPO" ls-files -s 2>/dev/null | awk '$1=="100755"{print $4}' | (cd "$SG_REPO" && xargs -r chmod +x)
  chmod +x "$SG_DIR"/*.sh "$SG_DIR"/*.py "$SG_DIR"/gitx "$SG_DIR"/hooks/* 2>/dev/null
  [ -L "$SG_HOME/tools" ] || { [ -e "$SG_HOME/tools" ] && mv "$SG_HOME/tools" "$SG_HOME/tools.old.$$"; ln -s "$SG_REPO/tools" "$SG_HOME/tools"; }
  if [ -z "$(git -C "$SG_REPO" config --get remote.origin.url 2>/dev/null)" ]; then
    git -C "$SG_REPO" config remote.origin.url "$SG_URL"
    git -C "$SG_REPO" config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
    git -C "$SG_REPO" config branch.main.remote origin; git -C "$SG_REPO" config branch.main.merge refs/heads/main
  fi
  local k; for k in $(git -C "$SG_REPO" config --name-only --get-regexp '^remote\..*\.url$' 2>/dev/null); do
    case "$(git -C "$SG_REPO" config --get "$k")" in *://*@*) git -C "$SG_REPO" config "$k" "$SG_URL";; esac
  done
  git -C "$SG_REPO" config --unset-all http.https://github.com/.extraheader 2>/dev/null || true
  git -C "$SG_REPO" config user.name arena-agent; git -C "$SG_REPO" config user.email agent@users.noreply.github.com
  git -C "$SG_REPO" config core.hooksPath "$SG_DIR/hooks"
  git -C "$SG_REPO" config credential.helper "$SG_VAULT/git-cred.sh"
}

sg_scanner_fix() { bash "$SG_REPO/tools/install-gitleaks.sh" >/dev/null 2>&1; [ -x "$SG_HOME/.cache/gitleaks/gitleaks" ]; }

sg_heal() {   # सब कुछ; कोई भी कदम विफल हो तो non-zero
  sg_vault_fix || return 1
  sg_install_helpers || return 1
  sg_repo_fix || return 1
  sg_scanner_fix || { echo "[secret-guard] gitleaks install नहीं हो सका — commit/push fail-closed रहेंगे" >&2; return 1; }
}

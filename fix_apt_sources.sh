#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  exec sudo -- "$0" "$@"
fi

source_file=/etc/apt/sources.list.d/ubuntu.sources
backup_dir=/etc/apt/source-backups
timestamp=$(date +%Y%m%d-%H%M%S)

install -d -m 0755 "$backup_dir"
if [[ -f "$source_file" ]]; then
  cp -a "$source_file" "$backup_dir/ubuntu.sources.$timestamp"
fi

cat >"$source_file" <<'EOF'
Types: deb
URIs: https://archive.ubuntu.com/ubuntu/
Suites: noble noble-updates noble-backports noble-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF

# APT scans only supported filenames here; move our earlier ad-hoc backup away.
if [[ -f /etc/apt/sources.list.d/ubuntu.sources.before-https ]]; then
  mv /etc/apt/sources.list.d/ubuntu.sources.before-https \
    "$backup_dir/ubuntu.sources.before-https.$timestamp"
fi

apt-get clean
apt-get update
apt-get install -y \
  build-essential git autoconf automake libtool pkg-config \
  texinfo gettext libxml2-dev libpcre2-dev zlib1g-dev \
  python3-dev swig

printf '\nInstalled package status:\n'
dpkg-query -W -f='${binary:Package}\t${db:Status-Abbrev}\t${Version}\n' \
  build-essential git autoconf automake libtool pkg-config \
  texinfo gettext libxml2-dev libpcre2-dev zlib1g-dev \
  python3-dev swig

#!/usr/bin/env bash
# Prepare le bundle PUIS le publie en production sur Vercel.
#
# Prerequis : etre connecte a Vercel (`npx vercel login`) sur le compte
# proprietaire du projet « edualert-bf ». Le projet existe deja : ce script
# ne le cree pas, il y pousse une nouvelle version de production.
#
# Usage : bash deploiement/vercel/deployer.sh
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$ICI/preparer.sh"

cd "$ICI/.build"
echo "== Rattachement au projet edualert-bf =="
npx -y vercel link --yes --project edualert-bf >/dev/null

echo "== Envoi en production =="
npx -y vercel deploy --prod --yes

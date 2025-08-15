#!/usr/bin/env bash

set -uoe pipefail

DRY_RUN=0
PUSH=""

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --*)
      case "$1" in
        --no-push)
          PUSH=0
          shift
          ;;
        --push)
          PUSH=1
          shift
          ;;
        *)
          echo "Unknown option: $1"
          exit 1
          ;;
      esac
      ;;
    *)
      echo "Unknown positional argument: $1, Possible values: major|minor|patch"
      exit 1
      ;;
  esac
done

cd "$(dirname "$0")"
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "File is not in git folder."
  echo "Please, properly mount nebius/pysdk repository and call this script from it."
  exit 1
fi
cd $(git rev-parse --show-toplevel)

if ! (git branch -r --contains HEAD | grep -q "\borigin/main\b"); then
  echo "Publish is possible only from the main branch. Current branches:"
  git --no-pager branch --contains HEAD
  exit 2
fi
if [[ -n $(git status --porcelain) ]]; then
  echo "Working tree is dirty. Publish is not possible"
  exit 3
fi

app_version=$(python src/scripts/version_updater.py pyproject.toml src/nebius/base/version.py print)

echo "Tagging commit $(git rev-parse HEAD) with version v$app_version"
git tag "v$app_version"

if [[ -z "$PUSH" ]]; then
  echo ""
  echo ""
  read -r -p "Push the tag to origin? (y/n): " CHOICE

  case "$CHOICE" in
    y|Y|yes|YES)
      PUSH=1
      ;;
    *)
      PUSH=0
  esac
  echo ""
  echo ""
fi

if [[ "$PUSH" == "1" ]]; then
  git push origin "v$app_version"
else
  echo "Do not forget to do:"
  echo "  git push origin \"v$app_version\""
  echo "or"
  echo "  git push origin --tags"
fi
